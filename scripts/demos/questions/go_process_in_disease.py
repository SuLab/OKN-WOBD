#!/usr/bin/env python3
"""
Q3: Which genes in a GO process are dysregulated in a disease, and which
    cell types drive the changes?

Data Sources: Ubergraph, Wikidata, CellxGene Census, ARCHS4
Primary Tools: go_disease_analysis engine (analysis_tools.go_disease_analysis)

Uses the promoted GO-Disease Analyzer to discover genes annotated to a GO
biological process term, analyze their single-cell expression in disease
vs normal tissue, and validate in bulk RNA-seq.

Usage:
    python -m questions.go_process_in_disease
    python -m questions.go_process_in_disease --go-term GO:0006954 --disease "rheumatoid arthritis" --tissue "synovial tissue"
"""

import argparse
from pathlib import Path

QUESTION = "Which {go_label} genes are dysregulated in {disease}, and which cell types drive the changes?"
GO_TERM = "GO:0030198"
GO_LABEL = "extracellular matrix organization"
DISEASE = "pulmonary fibrosis"
TISSUE = "lung"


def run(
    go_term: str = GO_TERM,
    go_label: str = GO_LABEL,
    disease: str = DISEASE,
    tissue: str = TISSUE,
    output_dir: str = "questions/output",
):
    """Run the investigation and produce an HTML report."""
    from analysis_tools.go_disease_analysis import run_analysis
    from questions._report import QuestionReport, results_table, summary_stats

    question = QUESTION.format(go_label=go_label, disease=disease)
    report = QuestionReport(
        question=question,
        sources=["Ubergraph", "Wikidata", "CellxGene Census", "ARCHS4"],
        module_name="go_process_in_disease",
    )

    # Run the multi-layer analysis engine
    print(f"Running GO-Disease analysis: {go_term} in {disease}...")
    result = run_analysis(
        go_term=go_term,
        disease=disease,
        tissue=tissue,
        go_label=go_label,
    )

    # --- Step 1: Gene Discovery ---
    layer1 = result.get("layer1_knowledge", {})
    n_genes = layer1.get("n_genes", 0)
    sample_genes = layer1.get("sample_genes", [])

    report.add_step(
        f"Discover genes annotated to {go_term} ({go_label})",
        summary_stats("Genes found", n_genes)
        + summary_stats("Sample", ", ".join(sample_genes[:10])),
        data=layer1,
    )

    # --- Step 2: Single-Cell Expression ---
    layer2 = result.get("layer2_singlecell", {})
    if not layer2.get("skipped"):
        upreg = layer2.get("top_upregulated", [])
        upreg_rows = [
            {"Gene": g["symbol"], "Max Fold Change": f"{g['fold_change']:.1f}x",
             "Top Cell Type": g.get("top_cell_type", "")}
            for g in upreg[:10]
        ]

        drivers = layer2.get("cell_type_drivers", [])
        driver_rows = [
            {"Cell Type": d["cell_type"],
             "Upregulated": str(d["n_upregulated"]),
             "Downregulated": str(d["n_downregulated"])}
            for d in drivers[:8]
        ]

        report.add_step(
            f"Analyze single-cell expression in {tissue} ({disease} vs normal)",
            summary_stats("Genes analyzed", layer2.get("n_genes_analyzed", 0))
            + summary_stats("Upregulated", layer2.get("n_upregulated", 0))
            + summary_stats("Downregulated", layer2.get("n_downregulated", 0))
            + "<h4>Top Upregulated Genes</h4>"
            + results_table(upreg_rows)
            + "<h4>Cell Type Drivers</h4>"
            + results_table(driver_rows),
        )
    else:
        report.add_step(
            "Single-cell expression analysis (skipped)",
            '<p class="no-data">CellxGene Census not available</p>',
        )

    # --- Step 3: Bulk Validation ---
    layer3 = result.get("layer3_validation", {})
    if layer3.get("available") and layer3.get("n_studies", 0) > 0:
        de_results = layer3.get("differential_expression", [])
        de_rows = [
            {"Gene": d["gene"],
             "Fold Change": f"{d['fold_change']:.1f}x",
             "Mean Disease": f"{d['mean_disease']:.0f}",
             "Mean Control": f"{d['mean_control']:.0f}",
             "Disease Studies": str(d.get("n_disease_studies", 0))}
            for d in de_results[:10]
        ]

        studies = layer3.get("studies", [])
        study_rows = [
            {"GEO Series": s["gse"],
             "Samples": str(s["n_samples"]),
             "Genes Detected": str(s["n_genes_detected"])}
            for s in studies[:5]
        ]

        report.add_step(
            "Validate in bulk RNA-seq (ARCHS4)",
            summary_stats("Disease studies", layer3.get("n_studies", 0))
            + summary_stats("Control samples", layer3.get("n_control_samples_with_data", 0))
            + "<h4>Differential Expression</h4>"
            + results_table(de_rows)
            + "<h4>Studies Used</h4>"
            + results_table(study_rows),
        )
    elif layer3.get("skipped"):
        report.add_step(
            "Bulk RNA-seq validation (skipped)",
            '<p class="no-data">ARCHS4 not available or skipped</p>',
        )
    else:
        report.add_step(
            "Bulk RNA-seq validation",
            summary_stats("Status", layer3.get("reason", "No studies found")),
        )

    # --- Step 4: LLM Summary (if available) ---
    llm_summary = result.get("llm_summary")
    if llm_summary:
        report.add_step(
            "LLM-generated scientific summary",
            f"<p>{llm_summary}</p>",
        )

    # --- Answer ---
    answer_parts = [
        f"Analysis of {n_genes} genes annotated to {go_label} ({go_term}) "
        f"in the context of {disease} in {tissue} tissue."
    ]
    if not layer2.get("skipped"):
        answer_parts.append(
            f"{layer2.get('n_upregulated', 0)} genes are upregulated and "
            f"{layer2.get('n_downregulated', 0)} are downregulated at the single-cell level."
        )
    report.set_answer("\n\n".join(answer_parts))

    report.add_provenance("go_term", go_term)
    report.add_provenance("disease", disease)
    report.add_provenance("tissue", tissue)

    filepath = str(Path(output_dir) / "go_process_in_disease.html")
    saved = report.save(filepath)
    print(f"Report saved to: {saved}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Which genes in a GO process are dysregulated in a disease?"
    )
    parser.add_argument("--go-term", default=GO_TERM, help=f"GO term ID (default: {GO_TERM})")
    parser.add_argument("--go-label", default=GO_LABEL, help=f"GO term label (default: {GO_LABEL})")
    parser.add_argument("--disease", default=DISEASE, help=f"Disease name (default: {DISEASE})")
    parser.add_argument("--tissue", default=TISSUE, help=f"Tissue name (default: {TISSUE})")
    parser.add_argument("--output-dir", "-o", default="questions/output")
    args = parser.parse_args()
    run(
        go_term=args.go_term,
        go_label=args.go_label,
        disease=args.disease,
        tissue=args.tissue,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
