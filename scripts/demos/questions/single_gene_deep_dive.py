#!/usr/bin/env python3
"""
Q7: What is a gene's role in a disease across cell types and data sources?

Data Sources: Wikidata, CellxGene Census, NIAID, ARCHS4
Primary Tools: SPARQLClient, CellxGeneClient, NIAIDClient, ARCHS4Client

Composes all four data source clients to build a comprehensive picture of
a single gene in a specific disease context: gene annotations, cell-type
expression changes, relevant studies, and bulk expression validation.

Usage:
    python -m questions.single_gene_deep_dive
    python -m questions.single_gene_deep_dive --gene COL1A1 --tissue liver --disease cirrhosis
"""

import argparse
import os
import re
from pathlib import Path
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

QUESTION = "What is {gene}'s role in {disease} across cell types and data sources?"
GENE = "ACTA2"
TISSUE = "lung"
DISEASE = "pulmonary fibrosis"


def run(
    gene: str = GENE,
    tissue: str = TISSUE,
    disease: str = DISEASE,
    output_dir: str = "questions/output",
):
    """Run the investigation and produce an HTML report."""
    from questions._report import QuestionReport, results_table, summary_stats

    question = QUESTION.format(gene=gene, disease=disease)
    report = QuestionReport(
        question=question,
        sources=["Wikidata", "CellxGene Census", "NIAID", "ARCHS4"],
        module_name="single_gene_deep_dive",
    )

    # --- Step 1: Gene context from Wikidata ---
    print(f"Step 1: Gene information for {gene}...")
    from clients import SPARQLClient
    sparql = SPARQLClient()

    try:
        gene_info = sparql.get_gene_info(gene)
    except Exception as e:
        gene_info = {}

    if gene_info:
        info_rows = []
        if gene_info.get("name"):
            info_rows.append({"Field": "Full Name", "Value": gene_info["name"]})
        if gene_info.get("entrez_id"):
            info_rows.append({"Field": "Entrez ID", "Value": gene_info["entrez_id"]})
        if gene_info.get("ensembl_id"):
            info_rows.append({"Field": "Ensembl ID", "Value": gene_info["ensembl_id"]})
        if gene_info.get("uniprot_ids"):
            info_rows.append({"Field": "UniProt", "Value": ", ".join(gene_info["uniprot_ids"][:3])})
        if gene_info.get("go_terms"):
            info_rows.append({"Field": "GO Terms", "Value": str(len(gene_info["go_terms"]))})

        report.add_step(
            f"Gene annotations from Wikidata",
            results_table(info_rows),
            data=gene_info,
        )
    else:
        report.add_step(
            "Gene annotations from Wikidata",
            f'<p class="no-data">No information found for {gene}</p>',
        )

    # --- Step 2: Single-cell expression ---
    print(f"Step 2: CellxGene expression for {gene} in {tissue}...")
    try:
        from clients import CellxGeneClient
        with CellxGeneClient() as cellxgene:
            comparison = cellxgene.compare_conditions(
                gene, tissue=tissue,
                condition_a="normal", condition_b=disease,
            )

            if comparison:
                comp_rows = [
                    {"Metric": "Normal mean", "Value": f"{comparison.mean_a:.2f}"},
                    {"Metric": f"{disease} mean", "Value": f"{comparison.mean_b:.2f}"},
                    {"Metric": "Fold change", "Value": f"{comparison.fold_change:.2f}x"},
                    {"Metric": "log2 FC", "Value": f"{comparison.log2_fold_change:.2f}"},
                    {"Metric": "Normal cells", "Value": f"{comparison.n_cells_a:,}"},
                    {"Metric": f"{disease} cells", "Value": f"{comparison.n_cells_b:,}"},
                ]
                if comparison.p_value is not None:
                    comp_rows.append({"Metric": "P-value", "Value": f"{comparison.p_value:.2e}"})

                report.add_step(
                    f"Overall expression: {disease} vs normal ({tissue})",
                    results_table(comp_rows),
                )

            # Cell type breakdown
            ct_data = cellxgene.get_cell_type_comparison(
                gene, tissue=tissue,
                condition_a="normal", condition_b=disease,
            )

            if ct_data:
                sorted_cts = sorted(ct_data.items(), key=lambda x: x[1].get("fold_change", 0), reverse=True)
                ct_rows = [
                    {"Cell Type": ct,
                     "Fold Change": f"{data['fold_change']:.2f}x",
                     "Normal": f"{data['mean_normal']:.1f}",
                     "Disease": f"{data['mean_disease']:.1f}",
                     "Cells (N+D)": f"{data['n_cells_normal']+data['n_cells_disease']:,}"}
                    for ct, data in sorted_cts[:12]
                ]
                report.add_step(
                    "Cell-type-specific expression changes",
                    results_table(ct_rows),
                )
            else:
                report.add_step(
                    "Cell-type-specific expression",
                    '<p class="no-data">No cell type data available</p>',
                )
    except ImportError:
        report.add_step(
            "Single-cell expression (CellxGene)",
            '<p class="no-data">cellxgene-census not installed</p>',
        )
    except Exception as e:
        report.add_step(
            "Single-cell expression (CellxGene)",
            f'<p class="no-data">Error: {e}</p>',
        )

    # --- Step 3: NIAID study discovery ---
    print(f"Step 3: Searching NIAID for {tissue} {disease} studies...")
    from clients import NIAIDClient
    niaid = NIAIDClient()
    geo_accessions = []

    try:
        result = niaid.search(
            f'{tissue} {disease} AND includedInDataCatalog.name:"NCBI GEO"',
            size=50,
        )

        geo_pattern = re.compile(r'(GSE\d+)')
        seen = set()
        for hit in result.hits:
            for field in [hit.get("identifier", ""), hit.get("url", ""),
                          str(hit.get("sameAs", [])), str(hit.get("distribution", []))]:
                if isinstance(field, str):
                    for m in geo_pattern.findall(field):
                        if m not in seen:
                            geo_accessions.append(m)
                            seen.add(m)

        report.add_step(
            f"Discover {disease} studies in NIAID",
            summary_stats("Total studies found", result.total)
            + summary_stats("With GEO accessions", len(geo_accessions))
            + (summary_stats("Sample GSEs", ", ".join(geo_accessions[:5])) if geo_accessions else ""),
        )
    except Exception as e:
        report.add_step(
            "Discover studies in NIAID",
            f'<p class="no-data">NIAID search failed: {e}</p>',
        )

    # --- Step 4: ARCHS4 bulk expression ---
    print(f"Step 4: Checking ARCHS4 for {gene} expression...")
    try:
        from clients import ARCHS4Client
        data_dir = os.environ.get("ARCHS4_DATA_DIR")
        h5_file = Path(data_dir) / "human_gene_v2.latest.h5" if data_dir else None

        if h5_file and h5_file.exists() and geo_accessions:
            archs4 = ARCHS4Client(organism="human", h5_path=str(h5_file))
            expr_rows = []

            for gse_id in geo_accessions[:10]:
                if archs4.has_series(gse_id):
                    try:
                        expr_df = archs4.get_expression_by_series(gse_id, genes=[gene])
                        if expr_df is not None and not expr_df.empty:
                            n_samples = expr_df.shape[1]
                            mean_expr = expr_df.iloc[0].mean()
                            expr_rows.append({
                                "GEO Series": gse_id,
                                "Samples": str(n_samples),
                                f"Mean {gene}": f"{mean_expr:.1f}",
                            })
                    except Exception:
                        pass

            if expr_rows:
                report.add_step(
                    f"Bulk expression of {gene} in ARCHS4",
                    summary_stats("Studies with data", len(expr_rows))
                    + results_table(expr_rows),
                )
            else:
                report.add_step(
                    f"Bulk expression of {gene} in ARCHS4",
                    '<p class="no-data">No matching studies found in ARCHS4 HDF5</p>',
                )
        else:
            reason = "ARCHS4 data not configured" if not h5_file else "No GEO accessions to query"
            report.add_step(
                f"Bulk expression of {gene} in ARCHS4",
                f'<p class="no-data">{reason}</p>',
            )
    except ImportError:
        report.add_step(
            f"Bulk expression of {gene} in ARCHS4",
            '<p class="no-data">ARCHS4 client not available</p>',
        )

    # --- Answer ---
    answer_parts = [f"Multi-source investigation of {gene} in {disease} ({tissue} tissue)."]
    if gene_info.get("name"):
        answer_parts.append(f"{gene} ({gene_info['name']}) was queried across 4 data layers.")
    if geo_accessions:
        answer_parts.append(f"Found {len(geo_accessions)} relevant GEO studies in NIAID.")
    report.set_answer("\n\n".join(answer_parts))

    report.add_provenance("gene_symbol", gene)
    report.add_provenance("tissue", tissue)
    report.add_provenance("disease", disease)

    # SPARQL query used
    report.add_query(
        "Wikidata: Gene information",
        f'''SELECT DISTINCT ?gene ?symbol ?entrez ?ensembl ?uniprot ?name ?description ?go_id WHERE {{
    ?gene wdt:P353 "{gene}" ;
          wdt:P703 wd:Q15978631 .
    OPTIONAL {{ ?gene wdt:P353 ?symbol . }}
    OPTIONAL {{ ?gene wdt:P351 ?entrez . }}
    OPTIONAL {{ ?gene wdt:P594 ?ensembl . }}
    OPTIONAL {{ ?gene rdfs:label ?name . FILTER(LANG(?name) = "en") }}
    OPTIONAL {{ ?gene schema:description ?description . FILTER(LANG(?description) = "en") }}
    OPTIONAL {{
        ?gene wdt:P702 ?protein .
        ?protein wdt:P352 ?uniprot .
    }}
    OPTIONAL {{
        ?gene wdt:P702 ?protein2 .
        ?protein2 wdt:P682 ?go_term .
        ?go_term wdt:P686 ?go_id .
    }}
}}''',
        "https://query.wikidata.org/sparql",
    )

    filepath = str(Path(output_dir) / "single_gene_deep_dive.html")
    saved = report.save(filepath)
    print(f"Report saved to: {saved}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Single gene deep dive across data sources")
    parser.add_argument("--gene", "-g", default=GENE, help=f"Gene symbol (default: {GENE})")
    parser.add_argument("--tissue", "-t", default=TISSUE, help=f"Tissue (default: {TISSUE})")
    parser.add_argument("--disease", "-d", default=DISEASE, help=f"Disease (default: {DISEASE})")
    parser.add_argument("--output-dir", "-o", default="questions/output")
    args = parser.parse_args()
    run(gene=args.gene.upper(), tissue=args.tissue,
        disease=args.disease, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
