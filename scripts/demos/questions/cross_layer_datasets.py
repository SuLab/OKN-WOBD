#!/usr/bin/env python3
"""
Q6: What genes from a biological process have expression data in relevant
    studies from the NIAID Data Ecosystem?

Data Sources: Wikidata, NIAID, ARCHS4
Primary Tools: SPARQLClient, NIAIDClient, ARCHS4Client

Demonstrates a cross-layer query: knowledge graph (gene annotations) ->
dataset discovery (NIAID) -> expression data (ARCHS4).

Usage:
    python -m questions.cross_layer_datasets
    python -m questions.cross_layer_datasets --go-term GO:0042113 --search "vaccination"
"""

import argparse
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

QUESTION = "What {go_label} genes have expression data in NIAID {search_term} studies?"
GO_TERM = "GO:0042113"
GO_LABEL = "B cell activation"
SEARCH_TERM = "vaccination"


def _extract_geo_accessions(hits: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Extract GSE accessions from NIAID hits. Returns (gse_id, study_name) tuples."""
    geo_pattern = re.compile(r'(GSE\d+)')
    accessions = []
    seen = set()
    for hit in hits:
        study_name = hit.get("name", "Unknown")[:60]
        for field in [hit.get("identifier", ""), hit.get("url", ""),
                      str(hit.get("sameAs", [])), str(hit.get("distribution", []))]:
            if isinstance(field, str):
                for m in geo_pattern.findall(field):
                    if m not in seen:
                        accessions.append((m, study_name))
                        seen.add(m)
    return accessions


def run(
    go_term: str = GO_TERM,
    go_label: str = GO_LABEL,
    search_term: str = SEARCH_TERM,
    output_dir: str = "questions/output",
):
    """Run the investigation and produce an HTML report."""
    from clients import SPARQLClient, NIAIDClient
    from questions._report import QuestionReport, results_table, summary_stats

    question = QUESTION.format(go_label=go_label, search_term=search_term)
    report = QuestionReport(
        question=question,
        sources=["Wikidata", "NIAID", "ARCHS4"],
        module_name="cross_layer_datasets",
    )

    # --- Step 1: Knowledge Layer ---
    print(f"Step 1: Querying Wikidata for {go_term} genes...")
    sparql = SPARQLClient()
    try:
        genes = sparql.get_genes_for_go_term(go_term)
        gene_symbols = [g["symbol"] for g in genes]
    except Exception as e:
        genes = []
        gene_symbols = []
        report.add_step(
            f"Query genes for {go_term} ({go_label})",
            f'<p class="no-data">Wikidata query failed: {e}</p>',
        )

    if gene_symbols:
        gene_rows = [{"Gene": s} for s in gene_symbols[:20]]
        report.add_step(
            f"Query genes annotated to {go_term} ({go_label})",
            summary_stats("Genes found", len(gene_symbols))
            + summary_stats("Sample", ", ".join(gene_symbols[:12]))
            + results_table(gene_rows, columns=["Gene"]),
        )

    # --- Step 2: Discovery Layer ---
    print(f"Step 2: Searching NIAID for '{search_term}' studies...")
    niaid = NIAIDClient()
    try:
        result = niaid.search(
            f'{search_term} AND includedInDataCatalog.name:"NCBI GEO"',
            size=50,
        )
        geo_accessions = _extract_geo_accessions(result.hits)
    except Exception as e:
        result = None
        geo_accessions = []
        report.add_step(
            f"Search NIAID for {search_term} studies",
            f'<p class="no-data">NIAID search failed: {e}</p>',
        )

    if result:
        study_rows = [
            {"GEO Series": gse, "Study": name}
            for gse, name in geo_accessions[:10]
        ]
        report.add_step(
            f"Search NIAID for {search_term} studies with GEO data",
            summary_stats("Total studies", result.total)
            + summary_stats("With GEO accessions", len(geo_accessions))
            + results_table(study_rows),
        )

    # --- Step 3: Data Layer ---
    print("Step 3: Checking ARCHS4 for expression data...")
    expression_df = None
    selected_gse = None

    try:
        from clients import ARCHS4Client
        data_dir = os.environ.get("ARCHS4_DATA_DIR")
        h5_file = Path(data_dir) / "human_gene_v2.latest.h5" if data_dir else None

        if h5_file and h5_file.exists() and gene_symbols and geo_accessions:
            archs4 = ARCHS4Client(organism="human", h5_path=str(h5_file))

            for gse_id, study_name in geo_accessions:
                if archs4.has_series(gse_id):
                    try:
                        expression_df = archs4.get_expression_by_series(
                            gse_id, genes=gene_symbols
                        )
                        if expression_df is not None and not expression_df.empty:
                            selected_gse = gse_id
                            break
                    except (ValueError, Exception):
                        continue

            if expression_df is not None and not expression_df.empty:
                genes_found = [g for g in gene_symbols if g in expression_df.index]
                sample_data = []
                for g in genes_found[:10]:
                    vals = expression_df.loc[g]
                    if hasattr(vals, 'mean'):
                        sample_data.append({"Gene": g, "Mean Expression": f"{vals.mean():.0f}",
                                            "Samples": str(len(vals))})

                report.add_step(
                    f"Retrieve expression from ARCHS4 ({selected_gse})",
                    summary_stats("GEO Series", selected_gse)
                    + summary_stats("Matrix size", f"{expression_df.shape[0]} genes x {expression_df.shape[1]} samples")
                    + summary_stats(f"{go_label} genes matched", len(genes_found))
                    + results_table(sample_data),
                )
            else:
                report.add_step(
                    "Retrieve expression from ARCHS4",
                    '<p class="no-data">No matching GEO series found in ARCHS4.</p>',
                )
        else:
            reason = "ARCHS4 data not configured" if not h5_file else "No genes or studies to query"
            report.add_step(
                "Retrieve expression from ARCHS4",
                f'<p class="no-data">{reason}</p>',
            )
    except ImportError:
        report.add_step(
            "Retrieve expression from ARCHS4",
            '<p class="no-data">ARCHS4 client not available (pip install h5py)</p>',
        )

    # --- Answer ---
    parts = [f"Found {len(gene_symbols)} genes annotated to {go_label} ({go_term})."]
    if geo_accessions:
        parts.append(f"Discovered {len(geo_accessions)} {search_term} studies with GEO data in NIAID.")
    if selected_gse and expression_df is not None:
        genes_matched = len([g for g in gene_symbols if g in expression_df.index])
        parts.append(
            f"Retrieved expression for {genes_matched} of {len(gene_symbols)} genes "
            f"from {selected_gse} ({expression_df.shape[1]} samples)."
        )
    report.set_answer("\n\n".join(parts))

    report.add_provenance("go_term", go_term)
    report.add_provenance("niaid_query", f'{search_term} AND includedInDataCatalog.name:"NCBI GEO"')
    if selected_gse:
        report.add_provenance("archs4_series", selected_gse)

    filepath = str(Path(output_dir) / "cross_layer_datasets.html")
    saved = report.save(filepath)
    print(f"Report saved to: {saved}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Cross-layer gene expression query")
    parser.add_argument("--go-term", default=GO_TERM, help=f"GO term (default: {GO_TERM})")
    parser.add_argument("--go-label", default=GO_LABEL, help=f"GO label (default: {GO_LABEL})")
    parser.add_argument("--search", default=SEARCH_TERM, help=f"NIAID search term (default: {SEARCH_TERM})")
    parser.add_argument("--output-dir", "-o", default="questions/output")
    args = parser.parse_args()
    run(go_term=args.go_term, go_label=args.go_label,
        search_term=args.search, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
