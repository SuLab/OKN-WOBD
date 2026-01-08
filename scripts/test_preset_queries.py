#!/usr/bin/env python3
"""Test preset queries against local RDF data using rdflib.

This script loads RDF files locally and tests the preset queries from
web/wobd_web/preset_queries.py against them. Useful for validating query
syntax and data links before loading into FRINK or other SPARQL endpoints.

Quick start:
    python scripts/test_preset_queries.py --verbose

For detailed usage, see docs/test_preset_queries_usage.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

# Add web directory to path so we can import preset_queries
sys.path.insert(0, str(Path(__file__).parent.parent / "web"))

from rdflib import Graph

from wobd_web.preset_queries import (
    DUSP2_UPREGULATION_QUERY,
    PRESET_QUERIES,
)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gene-expr-dir",
        type=Path,
        default=Path("data/gene_expression"),
        help="Directory containing gene expression .ttl files (default: data/gene_expression)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Test against a specific .ttl file (e.g., E-GEOD-76.ttl). If not specified, will use file-specific defaults or all files.",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Load all .ttl files instead of just the default for each query",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Test only a specific query by question text (exact match)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed query results",
    )
    parser.add_argument(
        "--limit-results",
        type=int,
        default=10,
        help="Maximum number of results to show per query (default: 10)",
    )
    return parser.parse_args(argv)


def load_gene_expression_graph(
    gene_expr_dir: Path, 
    specific_file: str | None = None,
    all_files: bool = False
) -> Graph:
    """Load gene expression .ttl file(s) from directory into a single graph.
    
    Args:
        gene_expr_dir: Directory containing .ttl files
        specific_file: If specified, load only this file (e.g., "E-GEOD-76.ttl")
        all_files: If True, load all files regardless of specific_file
    """
    graph = Graph()
    
    if not gene_expr_dir.is_dir():
        raise SystemExit(f"Gene expression directory not found: {gene_expr_dir}")
    
    if specific_file:
        # Load specific file
        ttl_file = gene_expr_dir / specific_file
        if not ttl_file.exists():
            raise SystemExit(f"File not found: {ttl_file}")
        ttl_files = [ttl_file]
    elif all_files:
        # Load all files
        ttl_files = sorted(gene_expr_dir.glob("*.ttl"))
        if not ttl_files:
            raise SystemExit(f"No .ttl files found in {gene_expr_dir}")
    else:
        # Default: use query-specific files (for now just Dusp2 query uses E-GEOD-76.ttl)
        # This will be determined by the query being tested
        ttl_files = []
    
    if not ttl_files:
        raise SystemExit("No files to load. Use --file or --all-files, or specify a query with a default file.")
    
    print(f"Loading gene expression data from {len(ttl_files)} file(s)...")
    for ttl_file in ttl_files:
        try:
            graph.parse(str(ttl_file), format="turtle")
            print(f"  ✓ {ttl_file.name}")
        except Exception as e:
            print(f"  ✗ {ttl_file.name}: {e}", file=sys.stderr)
    
    print(f"Loaded {len(graph)} triples\n")
    return graph


def test_query(
    graph: Graph,
    question: str,
    query: str,
    verbose: bool = False,
    limit_results: int = 10,
) -> tuple[bool, str]:
    """Test a SPARQL query against the graph.
    
    Returns (success, message) tuple.
    """
    try:
        result = graph.query(query)
        
        if result.type != "SELECT":
            return False, f"✗ Expected SELECT query, got {result.type}"
        
        rows = list(result)
        count = len(rows)
        message = f"✓ Executed successfully: {count} result(s)"
        
        if verbose and rows:
            message += "\n\n  Sample results:"
            # Show limited results
            for i, row in enumerate(rows[:limit_results], 1):
                # Convert row to dict for display
                row_dict = {}
                for key in row.labels:
                    value = row[key]
                    if value:
                        # Format URI values more readably
                        value_str = str(value)
                        if value_str.startswith("http"):
                            # Extract identifier from URI if possible
                            if "/" in value_str:
                                value_str = value_str.split("/")[-1]
                                if "#" in value_str:
                                    value_str = value_str.split("#")[-1]
                        row_dict[key] = value_str
                    else:
                        row_dict[key] = None
                message += f"\n    {i}. {row_dict}"
            
            if count > limit_results:
                message += f"\n    ... and {count - limit_results} more"
        
        return True, message
        
    except Exception as e:
        error_msg = str(e)
        # Add helpful hints for common errors
        if "CONTAINS" in error_msg or "contains" in error_msg:
            error_msg += "\n    (Hint: rdflib supports CONTAINS - this might be a data/query structure issue)"
        elif "REPLACE" in error_msg or "replace" in error_msg:
            error_msg += "\n    (Hint: Check REPLACE regex pattern syntax)"
        
        return False, f"✗ Error: {error_msg}"


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    
    # Filter queries based on what data we're testing against
    # For now, focus on gene expression queries
    # Map queries to their default data files (if any)
    from wobd_web.preset_queries import SFRP2_EXPRESSION_STUDIES_QUERY
    
    gene_expr_queries = {
        "Find experiments where Dusp2 is upregulated.": DUSP2_UPREGULATION_QUERY,
        "Find studies where SFRP2 is upregulated or downregulated.": SFRP2_EXPRESSION_STUDIES_QUERY,
    }
    
    # Map queries to their default data files
    # Note: SFRP2 associations may be across multiple files, so no single default file
    query_default_files = {
        "Find experiments where Dusp2 is upregulated.": "E-GEOD-10311.ttl",  # Dusp2 associations are in this file
    }
    
    # If specific query requested, test only that
    if args.query:
        if args.query not in gene_expr_queries:
            print(f"Error: Query '{args.query}' not found in available queries.")
            print(f"Available queries: {list(gene_expr_queries.keys())}")
            return 1
        queries_to_test = {args.query: gene_expr_queries[args.query]}
    else:
        queries_to_test = gene_expr_queries
    
    if not queries_to_test:
        print("No queries to test.")
        return 0
    
    # Determine which file(s) to load
    # Priority: --file > --all-files > query-specific default
    specific_file = args.file
    if not specific_file and not args.all_files:
        if len(queries_to_test) == 1:
            # Use default file for the query if only testing one query
            query_text = list(queries_to_test.keys())[0]
            default_file = query_default_files.get(query_text)
            if default_file:
                specific_file = default_file
                print(f"Using default file for query: {specific_file}\n")
            else:
                # Query has no default file - need user to specify
                print(f"Error: Query '{query_text}' has no default file.")
                if "SFRP2" in query_text:
                    print("\nSFRP2 associations are spread across multiple files.")
                    print("Please use one of the following options:\n")
                    print("  --all-files          Test against all files (recommended)")
                    print("  --file <filename>    Test against a specific file\n")
                else:
                    print("Please use --file <specific-file> or --all-files to specify data source.\n")
                return 1
    
    # Load gene expression data
    try:
        graph = load_gene_expression_graph(
            args.gene_expr_dir, 
            specific_file=specific_file,
            all_files=args.all_files
        )
    except SystemExit as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    # Test each query
    print(f"Testing {len(queries_to_test)} query(ies)...\n")
    all_passed = True
    
    for question, query in queries_to_test.items():
        print(f"Query: {question}")
        print("-" * 80)
        
        success, message = test_query(
            graph, question, query, 
            verbose=args.verbose,
            limit_results=args.limit_results
        )
        
        if not success:
            all_passed = False
        
        print(message)
        print()
    
    if all_passed:
        print("✓ All queries passed!")
        return 0
    else:
        print("✗ Some queries failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

