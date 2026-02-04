#!/usr/bin/env python3
"""Run a SPARQL query against local RDF files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from rdflib import Graph


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query_file",
        type=Path,
        help="Path to SPARQL query file",
    )
    parser.add_argument(
        "--rdf-dir",
        type=Path,
        default=Path("data/rdf"),
        help="Directory containing RDF .nt files (default: data/rdf)",
    )
    parser.add_argument(
        "--rdf-file",
        type=Path,
        help="Specific RDF .nt file to query (overrides --rdf-dir)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Override LIMIT in query (if any)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    
    # Load query
    query_text = args.query_file.read_text()
    
    # Override LIMIT if requested
    if args.limit is not None:
        # Remove existing LIMIT clause if present
        import re
        query_text = re.sub(r'\s+LIMIT\s+\d+', '', query_text, flags=re.IGNORECASE)
        query_text = query_text.rstrip() + f'\nLIMIT {args.limit}'
    
    # Load RDF data
    graph = Graph()
    
    if args.rdf_file:
        # Load specific file
        print(f"Loading RDF from {args.rdf_file}...")
        graph.parse(args.rdf_file, format="nt")
    else:
        # Load all .nt files from directory
        rdf_files = sorted(args.rdf_dir.glob("*.nt"))
        if not rdf_files:
            print(f"Error: No .nt files found in {args.rdf_dir}")
            return 1
        
        print(f"Loading {len(rdf_files)} RDF file(s) from {args.rdf_dir}...")
        for rdf_file in rdf_files:
            graph.parse(rdf_file, format="nt")
    
    print(f"Loaded {len(graph)} triples\n")
    
    # Execute query
    print("Query:")
    print("-" * 80)
    print(query_text)
    print("-" * 80)
    print()
    
    results = graph.query(query_text)
    
    # Print results
    if results.type == "SELECT":
        # Print header
        print("Results:")
        print("=" * 80)
        headers = [str(var) for var in results.vars]
        print(" | ".join(f"{h:30}" for h in headers))
        print("-" * 80)
        
        # Print rows
        count = 0
        for row in results:
            values = [str(val) if val else "" for val in row]
            print(" | ".join(f"{v[:30]:30}" for v in values))
            count += 1
        
        print("-" * 80)
        print(f"Total: {count} result(s)")
        
    elif results.type == "ASK":
        print(f"Result: {bool(results)}")
        
    elif results.type == "CONSTRUCT" or results.type == "DESCRIBE":
        print(f"Result: {len(results)} triple(s)")
        for triple in results:
            print(f"  {triple}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
