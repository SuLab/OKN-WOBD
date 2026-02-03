#!/usr/bin/env python3
"""
Runner for all biological question modules.

Discovers and runs question modules, producing individual HTML reports
and an index page linking to all of them.

Usage:
    python -m questions.run_all              # Run all questions
    python -m questions.run_all --list       # List available questions
    python -m questions.run_all --question gene_disease_map   # Run one
    python -m questions.run_all --output-dir custom/path
"""

import argparse
import importlib
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Registry of question modules: (module_name, short_label, requires)
QUESTIONS = [
    ("gene_disease_map", "Q1: Gene-Disease Map", ["SPARQLWrapper"]),
    ("gene_neighborhood_map", "Q2: Gene Neighborhood", ["SPARQLWrapper"]),
    ("go_process_in_disease", "Q3: GO Process in Disease", ["SPARQLWrapper"]),
    ("differential_expression", "Q4: Differential Expression", ["chatgeo"]),
    ("drug_disease_targets", "Q5: Drug-Disease Targets", ["GXA/Fuseki"]),
    ("cross_layer_datasets", "Q6: Cross-Layer Datasets", ["SPARQLWrapper"]),
    ("single_gene_deep_dive", "Q7: Single Gene Deep Dive", ["SPARQLWrapper"]),
]


def list_questions() -> None:
    """Print all available question modules."""
    print("Available questions:\n")
    for module_name, label, requires in QUESTIONS:
        reqs = ", ".join(requires)
        print(f"  {module_name:30s}  {label}  (requires: {reqs})")
    print(f"\nRun with: python -m questions.run_all --question <module_name>")


def run_question(module_name: str, output_dir: str) -> Optional[Dict[str, Any]]:
    """Import and run a single question module. Returns result info or None on error."""
    try:
        mod = importlib.import_module(f"questions.{module_name}")
        question_text = getattr(mod, "QUESTION", module_name)
        print(f"\n{'='*70}")
        print(f"Running: {module_name}")
        print(f"  {question_text}")
        print(f"{'='*70}\n")

        mod.run(output_dir=output_dir)

        return {
            "module": module_name,
            "question": question_text,
            "status": "success",
            "output": f"{module_name}.html",
        }

    except Exception as e:
        print(f"\n  ERROR in {module_name}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {
            "module": module_name,
            "question": module_name,
            "status": f"error: {e}",
            "output": None,
        }


def generate_index(results: List[Dict[str, Any]], output_dir: str) -> str:
    """Generate an index.html linking to all question reports."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_html = []
    for r in results:
        status_class = "success" if r["status"] == "success" else "error"
        link = f'<a href="{r["output"]}">{r["module"]}</a>' if r["output"] else r["module"]
        status_badge = "OK" if r["status"] == "success" else r["status"]

        rows_html.append(f"""
        <tr>
            <td>{link}</td>
            <td>{r.get("question", "")}</td>
            <td class="{status_class}">{status_badge}</td>
        </tr>""")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OKN-WOBD Biological Questions</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            color: #2c3e50;
        }}
        h1 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ padding: 10px 14px; border: 1px solid #e9ecef; text-align: left; }}
        th {{ background: #f8f9fa; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .success {{ color: #27ae60; font-weight: 600; }}
        .error {{ color: #e74c3c; font-size: 0.85em; }}
        footer {{ margin-top: 30px; font-size: 0.85em; color: #999; }}
    </style>
</head>
<body>
    <h1>OKN-WOBD: Biological Questions</h1>
    <p>Each question is a self-contained investigation that queries multiple
    biomedical data sources and produces an interactive HTML report.</p>

    <table>
        <thead>
            <tr><th>Module</th><th>Question</th><th>Status</th></tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>

    <footer>Generated: {timestamp}</footer>
</body>
</html>'''

    index_path = Path(output_dir) / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html)
    return str(index_path.resolve())


def main():
    parser = argparse.ArgumentParser(
        description="Run biological question investigations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list", action="store_true", help="List available questions")
    parser.add_argument("--question", "-q", help="Run a single question by module name")
    parser.add_argument("--output-dir", "-o", default="questions/output",
                        help="Output directory for HTML reports")
    args = parser.parse_args()

    if args.list:
        list_questions()
        return

    output_dir = args.output_dir

    if args.question:
        # Run a single question
        valid_names = [q[0] for q in QUESTIONS]
        if args.question not in valid_names:
            print(f"Unknown question: {args.question}")
            print(f"Valid options: {', '.join(valid_names)}")
            sys.exit(1)
        run_question(args.question, output_dir)
        return

    # Run all questions
    print("Running all biological questions...")
    print(f"Output directory: {output_dir}\n")

    results = []
    for module_name, label, requires in QUESTIONS:
        result = run_question(module_name, output_dir)
        if result:
            results.append(result)

    # Generate index
    index_path = generate_index(results, output_dir)
    print(f"\n{'='*70}")
    print(f"Index page: {index_path}")
    print(f"{'='*70}")

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - succeeded
    print(f"\nResults: {succeeded} succeeded, {failed} failed out of {len(results)} questions")


if __name__ == "__main__":
    main()
