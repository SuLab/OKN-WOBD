#!/usr/bin/env python3
"""
Q4: What genes are differentially expressed in a disease tissue vs normal?

Data Sources: ARCHS4, g:Profiler
Primary Tools: chatgeo pipeline

Uses the ChatGEO pipeline to find matching samples in ARCHS4, run
differential expression analysis, and perform pathway enrichment.

Usage:
    python -m questions.differential_expression
    python -m questions.differential_expression --query "lung fibrosis" --tissue lung
"""

import argparse
import json
import sys
from pathlib import Path

QUESTION = "What genes are differentially expressed in {query} vs normal?"
QUERY = "psoriasis in skin tissue"


def run(query: str = QUERY, output_dir: str = "questions/output"):
    """Run the investigation and produce an HTML report."""
    from questions._report import QuestionReport, results_table, summary_stats

    question = QUESTION.format(query=query)
    report = QuestionReport(
        question=question,
        sources=["ARCHS4", "g:Profiler"],
        module_name="differential_expression",
    )

    # Import ChatGEO components
    try:
        from chatgeo.cli import parse_query, run_analysis as chatgeo_run
    except ImportError:
        report.add_step(
            "Import ChatGEO pipeline",
            '<p class="no-data">ChatGEO not available. Install dependencies: '
            "pip install pandas scipy numpy pydeseq2 gprofiler-official</p>",
        )
        report.set_answer("ChatGEO pipeline could not be loaded.")
        filepath = str(Path(output_dir) / "differential_expression.html")
        report.save(filepath)
        return report

    # --- Step 1: Parse query ---
    disease, tissue = parse_query(query)
    report.add_step(
        "Parse natural language query",
        summary_stats("Disease term", disease)
        + summary_stats("Tissue term", tissue or "auto-detected"),
    )

    # --- Step 2: Run ChatGEO analysis ---
    print(f"Running ChatGEO: disease={disease}, tissue={tissue}")
    try:
        result = chatgeo_run(
            disease=disease,
            tissue=tissue,
            output_path=None,
            verbose=False,
        )
    except Exception as e:
        report.add_step(
            "Run differential expression analysis",
            f'<p class="no-data">Analysis failed: {e}</p>',
        )
        report.set_answer(f"Differential expression analysis failed: {e}")
        filepath = str(Path(output_dir) / "differential_expression.html")
        report.save(filepath)
        return report

    if not result:
        report.add_step(
            "Run differential expression analysis",
            '<p class="no-data">No results returned from ChatGEO.</p>',
        )
        report.set_answer("No differentially expressed genes found.")
        filepath = str(Path(output_dir) / "differential_expression.html")
        report.save(filepath)
        return report

    # --- Step 3: Sample discovery ---
    sample_info = result.get("sample_discovery", {})
    report.add_step(
        "Discover disease and control samples in ARCHS4",
        summary_stats("Disease samples", sample_info.get("n_disease_samples", "N/A"))
        + summary_stats("Control samples", sample_info.get("n_control_samples", "N/A"))
        + summary_stats("Mode", sample_info.get("mode", "N/A")),
    )

    # --- Step 4: DE results ---
    de_results = result.get("de_results", {})
    sig_genes = de_results.get("significant_genes", [])

    if sig_genes:
        top_up = [g for g in sig_genes if g.get("log2_fold_change", 0) > 0][:10]
        top_down = [g for g in sig_genes if g.get("log2_fold_change", 0) < 0][:10]

        up_rows = [
            {"Gene": g["gene"], "log2FC": f"{g['log2_fold_change']:.2f}",
             "Adj. P-value": f"{g.get('padj', 0):.2e}"}
            for g in top_up
        ]
        down_rows = [
            {"Gene": g["gene"], "log2FC": f"{g['log2_fold_change']:.2f}",
             "Adj. P-value": f"{g.get('padj', 0):.2e}"}
            for g in top_down
        ]

        report.add_step(
            "Differential expression results",
            summary_stats("Total significant genes", len(sig_genes))
            + summary_stats("Upregulated", len([g for g in sig_genes if g.get("log2_fold_change", 0) > 0]))
            + summary_stats("Downregulated", len([g for g in sig_genes if g.get("log2_fold_change", 0) < 0]))
            + "<h4>Top Upregulated</h4>"
            + results_table(up_rows)
            + "<h4>Top Downregulated</h4>"
            + results_table(down_rows),
        )
    else:
        report.add_step(
            "Differential expression results",
            summary_stats("Significant genes", 0),
        )

    # --- Step 5: Enrichment ---
    enrichment = result.get("enrichment", {})
    go_terms = enrichment.get("GO:BP", [])
    if go_terms:
        go_rows = [
            {"Term": t.get("name", "")[:60], "P-value": f"{t.get('p_value', 0):.2e}",
             "Genes": str(t.get("intersection_size", ""))}
            for t in go_terms[:10]
        ]
        report.add_step(
            "Pathway enrichment (g:Profiler)",
            "<h4>Top GO Biological Processes</h4>" + results_table(go_rows),
        )

    kegg = enrichment.get("KEGG", [])
    if kegg:
        kegg_rows = [
            {"Pathway": t.get("name", "")[:60], "P-value": f"{t.get('p_value', 0):.2e}",
             "Genes": str(t.get("intersection_size", ""))}
            for t in kegg[:10]
        ]
        report.add_step(
            "KEGG pathway enrichment",
            results_table(kegg_rows),
        )

    # --- Answer ---
    n_sig = len(sig_genes) if sig_genes else 0
    report.set_answer(
        f"Differential expression analysis of {query} identified {n_sig} "
        f"significantly differentially expressed genes.\n\n"
        + (f"Top enriched GO process: {go_terms[0]['name']}" if go_terms else
           "No pathway enrichment results available.")
    )

    report.add_provenance("query", query)
    report.add_provenance("disease_term", disease)
    report.add_provenance("tissue_term", tissue or "auto")

    filepath = str(Path(output_dir) / "differential_expression.html")
    saved = report.save(filepath)
    print(f"Report saved to: {saved}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Differential expression analysis")
    parser.add_argument("--query", "-q", default=QUERY, help=f"Natural language query (default: {QUERY})")
    parser.add_argument("--output-dir", "-o", default="questions/output")
    args = parser.parse_args()
    run(query=args.query, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
