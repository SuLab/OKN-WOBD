#!/usr/bin/env python3
"""Test competency question SPARQL queries against local RDF data."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Namespace
from rdflib.query import Result


DEFAULT_RDF_DIR = Path("data/rdf")
DEFAULT_QUERIES_FILE = Path("docs/competency_questions.md")

# Common namespaces
SCHEMA = Namespace("http://schema.org/")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rdf-dir",
        type=Path,
        default=DEFAULT_RDF_DIR,
        help=f"Directory containing RDF .nt files (default: {DEFAULT_RDF_DIR})",
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        default=DEFAULT_QUERIES_FILE,
        help=f"Markdown file with competency questions (default: {DEFAULT_QUERIES_FILE})",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Test only a specific query (e.g., 'CQ2' or 'CQ10')",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show query results and detailed error messages",
    )
    return parser.parse_args(argv)


def extract_queries(markdown_file: Path) -> dict[str, tuple[str, str]]:
    """Extract SPARQL queries from markdown file.
    
    Returns a dict mapping query IDs (e.g., 'CQ2') to (question, query) tuples.
    """
    content = markdown_file.read_text(encoding="utf-8")
    queries: dict[str, tuple[str, str]] = {}
    
    # Pattern to match query sections: ### CQ#: Question
    pattern = r"### (CQ\d+):\s*(.+?)\n.*?```sparql\n(.*?)```"
    
    for match in re.finditer(pattern, content, re.DOTALL):
        cq_id = match.group(1)
        question = match.group(2).strip()
        query = match.group(3).strip()
        queries[cq_id] = (question, query)
    
    return queries


def load_rdf_graph(rdf_dir: Path) -> Graph:
    """Load all RDF files from directory into a single graph."""
    graph = Graph()
    
    if not rdf_dir.is_dir():
        raise SystemExit(f"RDF directory not found: {rdf_dir}")
    
    rdf_files = sorted(rdf_dir.glob("*.nt"))
    if not rdf_files:
        raise SystemExit(f"No .nt files found in {rdf_dir}")
    
    print(f"Loading RDF data from {len(rdf_files)} file(s)...")
    for rdf_file in rdf_files:
        print(f"  - {rdf_file.name}")
        graph.parse(str(rdf_file), format="nt")
    
    print(f"Loaded {len(graph)} triples\n")
    return graph


def test_query(
    graph: Graph,
    cq_id: str,
    question: str,
    query: str,
    verbose: bool = False,
) -> tuple[bool, str, Result | None]:
    """Test a SPARQL query against the graph.
    
    Returns (success, message, result) tuple.
    """
    try:
        result = graph.query(query)
        
        # Check if query executed successfully
        if result.type == "SELECT":
            rows = list(result)
            count = len(rows)
            message = f"✓ Executed successfully: {count} result(s)"
            
            if verbose and rows:
                message += "\n  Sample results:"
                # Show first 3 results
                for i, row in enumerate(rows[:3], 1):
                    # Convert row to dict for display
                    row_dict = {str(k): str(v) for k, v in row.asdict().items()}
                    message += f"\n    {i}. {row_dict}"
                if count > 3:
                    message += f"\n    ... and {count - 3} more"
        else:
            message = "✓ Executed successfully"
        
        return True, message, result
        
    except Exception as e:
        error_msg = str(e)
        if "CONTAINS" in error_msg or "contains" in error_msg:
            error_msg += " (Hint: Use REGEX instead of CONTAINS for Protege compatibility)"
        elif "REPLACE" in error_msg or "replace" in error_msg:
            error_msg += " (Hint: REPLACE may not be supported in older Protege versions)"
        
        return False, f"✗ Error: {error_msg}", None


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    
    # Extract queries from markdown
    print(f"Extracting queries from {args.queries_file}...")
    queries = extract_queries(args.queries_file)
    
    if not queries:
        raise SystemExit(f"No queries found in {args.queries_file}")
    
    print(f"Found {len(queries)} query(ies)\n")
    
    # Filter to specific query if requested
    if args.query:
        query_id = args.query.upper()
        if query_id not in queries:
            raise SystemExit(f"Query {query_id} not found. Available: {', '.join(sorted(queries.keys()))}")
        queries = {query_id: queries[query_id]}
    
    # Load RDF data
    graph = load_rdf_graph(args.rdf_dir)
    
    # Test each query
    print("Testing queries:\n")
    results: list[tuple[str, bool, str]] = []
    
    for cq_id in sorted(queries.keys()):
        question, query = queries[cq_id]
        print(f"{cq_id}: {question}")
        if args.verbose:
            print(f"Query:\n{query}\n")
        
        success, message, _ = test_query(graph, cq_id, question, query, args.verbose)
        print(f"  {message}\n")
        results.append((cq_id, success, message))
    
    # Summary
    print("=" * 60)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"Summary: {passed}/{total} query(ies) executed successfully")
    
    if passed < total:
        print("\nFailed queries:")
        for cq_id, success, message in results:
            if not success:
                print(f"  {cq_id}: {message}")
        return 1
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

