#!/usr/bin/env python3
"""
Q5: What genes show opposing drug vs disease expression, suggesting
    therapeutic potential?

Data Sources: GXA/Fuseki (local), SPOKE
Primary Tools: find_drug_disease_genes, PlotlyVisualizer

Queries a local GXA Fuseki server for genes where drug treatment pushes
expression in the opposite direction from disease, identifying potential
therapeutic mechanisms.

Requires: Local Fuseki server running at http://localhost:3030/GXA-v2/sparql

Usage:
    python -m questions.drug_disease_targets
"""

import argparse
from pathlib import Path

QUESTION = "What genes show opposing drug vs disease expression, suggesting therapeutic potential?"


def run(output_dir: str = "questions/output"):
    """Run the investigation and produce an HTML report."""
    from questions._report import QuestionReport, results_table, summary_stats

    report = QuestionReport(
        question=QUESTION,
        sources=["GXA/Fuseki", "SPOKE"],
        module_name="drug_disease_targets",
    )

    # Import analysis function
    try:
        from analysis_tools.drug_disease import find_drug_disease_genes, print_results
    except ImportError:
        report.add_step(
            "Import drug-disease analysis",
            '<p class="no-data">drug_disease module not available.</p>',
        )
        report.set_answer("Drug-disease analysis module could not be loaded.")
        filepath = str(Path(output_dir) / "drug_disease_targets.html")
        report.save(filepath)
        return report

    # --- Pattern 1: Drug DOWN, Disease UP ---
    print("Pattern 1: Drug DOWN-regulates / Disease UP-regulates...")
    try:
        results1, drug_label1, disease_label1 = find_drug_disease_genes(
            drug_direction="down", disease_direction="up"
        )
    except Exception as e:
        results1 = []
        report.add_step(
            "Pattern 1: Drug suppresses pathologically elevated genes",
            f'<p class="no-data">Query failed: {e}. Is the GXA Fuseki server running at localhost:3030?</p>',
        )
        report.set_answer(
            "Analysis requires a local GXA Fuseki server. "
            "Start it with: fuseki-server --mem /GXA-v2"
        )
        filepath = str(Path(output_dir) / "drug_disease_targets.html")
        report.save(filepath)
        return report

    if results1:
        p1_rows = [
            {"Gene": r["gene"],
             "Drug log2FC": f"{r['drug_log2fc']:.1f}",
             "Disease log2FC": f"{r['disease_log2fc']:.1f}",
             "Disease": r.get("disease", "")[:40],
             "Drug": (r.get("drug_name") or r.get("drug_test_group", ""))[:30]}
            for r in results1[:15]
        ]
        report.add_step(
            f"Pattern 1: Drug DOWN / Disease UP ({len(results1)} gene-disease pairs)",
            summary_stats("Gene-disease pairs", len(results1))
            + summary_stats("Unique genes", len(set(r["gene"] for r in results1)))
            + results_table(p1_rows),
        )

    # --- Pattern 2: Drug UP, Disease DOWN ---
    print("Pattern 2: Drug UP-regulates / Disease DOWN-regulates...")
    try:
        results2, drug_label2, disease_label2 = find_drug_disease_genes(
            drug_direction="up", disease_direction="down"
        )
    except Exception as e:
        results2 = []

    if results2:
        p2_rows = [
            {"Gene": r["gene"],
             "Drug log2FC": f"{r['drug_log2fc']:.1f}",
             "Disease log2FC": f"{r['disease_log2fc']:.1f}",
             "Disease": r.get("disease", "")[:40],
             "Drug": (r.get("drug_name") or r.get("drug_test_group", ""))[:30]}
            for r in results2[:15]
        ]
        report.add_step(
            f"Pattern 2: Drug UP / Disease DOWN ({len(results2)} gene-disease pairs)",
            summary_stats("Gene-disease pairs", len(results2))
            + summary_stats("Unique genes", len(set(r["gene"] for r in results2)))
            + results_table(p2_rows),
        )

    # --- Visualization ---
    try:
        from analysis_tools.visualization import PlotlyVisualizer
        viz = PlotlyVisualizer()

        if results1 or results2:
            fig = viz.drug_disease_patterns(results1[:15], results2[:15])
            chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
            report.add_visualization(
                "Drug vs Disease Expression Patterns",
                f'<div id="plotly-chart">{chart_html}</div>',
            )
    except Exception:
        pass

    # --- Answer ---
    total = len(results1) + len(results2)
    unique_genes = len(set(r["gene"] for r in results1) | set(r["gene"] for r in results2))
    report.set_answer(
        f"Found {total} gene-drug-disease combinations across {unique_genes} unique genes "
        f"with opposing expression patterns.\n\n"
        f"Pattern 1 (drug suppresses pathologically elevated genes): {len(results1)} pairs.\n"
        f"Pattern 2 (drug activates pathologically suppressed genes): {len(results2)} pairs."
    )

    report.add_provenance("gxa_endpoint", "http://localhost:3030/GXA-v2/sparql")

    filepath = str(Path(output_dir) / "drug_disease_targets.html")
    saved = report.save(filepath)
    print(f"Report saved to: {saved}")
    return report


def main():
    parser = argparse.ArgumentParser(description=QUESTION)
    parser.add_argument("--output-dir", "-o", default="questions/output")
    args = parser.parse_args()
    run(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
