#!/usr/bin/env python3
"""Verify GXA SPARQL query against local RDF data.

Runs the WOBD genes-in-experiment query against local TTL files in data/gene_expression/
to compare with Expression Atlas website results. Useful for debugging discrepancies
between WOBD/OKN graph and live GXA data.

Usage:
    python scripts/verify_gxa_query_local.py
    python scripts/verify_gxa_query_local.py --experiment E-GEOD-76 --contrast "1 hour"
    python scripts/verify_gxa_query_local.py --list-contrasts  # List all contrast labels
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from rdflib import Graph


# Base query: DE genes for experiment, optionally filtered by contrast label
# No fold-change or p-value cutoffs (matches WOBD default)
QUERY_BASE = """
PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT
  ?experimentId
  ?contrast
  ?contrastId
  ?contrastLabel
  ?gene
  ?geneSymbol
  ?log2fc
  ?adjPValue
WHERE {
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast ;
         spokegenelab:log2fc ?log2fc .
  OPTIONAL { ?assoc spokegenelab:adj_p_value ?adjPValue . }
  ?contrast a biolink:Assay .
  FILTER(CONTAINS(STR(?contrast), "%(experiment)s"))
  
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast spokegenelab:contrast_id ?contrastIdProp . }
  BIND(COALESCE(?contrastIdProp, REPLACE(STR(?contrast), "^.*-(g[0-9]+_g[0-9]+)$", "$1")) AS ?contrastId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
  %(contrast_filter)s
}
ORDER BY ?contrastId ?geneSymbol
LIMIT %(limit)s
"""

# Query to list all contrast labels in an experiment
QUERY_LIST_CONTRASTS = """
PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT ?contrastId ?contrastLabel (COUNT(?gene) AS ?geneCount)
WHERE {
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
  ?contrast a biolink:Assay .
  FILTER(CONTAINS(STR(?contrast), "%(experiment)s"))
  OPTIONAL { ?contrast spokegenelab:contrast_id ?contrastIdProp . }
  BIND(COALESCE(?contrastIdProp, REPLACE(STR(?contrast), "^.*-(g[0-9]+_g[0-9]+)$", "$1")) AS ?contrastId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
}
GROUP BY ?contrastId ?contrastLabel
ORDER BY ?contrastId
"""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gene-expr-dir",
        type=Path,
        default=Path("data/gene_expression"),
        help="Directory containing .ttl files",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="E-GEOD-76",
        help="Experiment accession (e.g. E-GEOD-76)",
    )
    parser.add_argument(
        "--contrast",
        type=str,
        default=None,
        help="Filter contrast by substring (e.g. '1 hour' for aortic banding 1h vs sham 1h)",
    )
    parser.add_argument(
        "--min-abs-log2fc",
        type=float,
        default=None,
        help="Min |log2fc| to match GXA cutoff (e.g. 0.6 for foldChange 0.6)",
    )
    parser.add_argument(
        "--max-adj-p-value",
        type=float,
        default=None,
        help="Max adj p-value (e.g. 0.05)",
    )
    parser.add_argument(
        "--list-contrasts",
        action="store_true",
        help="List all contrast labels and gene counts instead of running DE query",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max rows to return",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show sample results",
    )
    parser.add_argument(
        "--export-csv",
        type=Path,
        default=None,
        metavar="FILE",
        help="Export results to CSV (geneSymbol,log2fc,adjPValue,contrastLabel) for comparison with GXA",
    )
    return parser.parse_args(argv)


def load_graph(gene_expr_dir: Path, experiment: str) -> Graph:
    ttl_file = gene_expr_dir / f"{experiment}.ttl"
    if not ttl_file.exists():
        raise SystemExit(f"File not found: {ttl_file}")
    graph = Graph()
    graph.parse(str(ttl_file), format="turtle")
    return graph


def run_query(graph: Graph, query: str) -> list:
    results = list(graph.query(query))
    return results


def main(argv=None):
    args = parse_args(argv)

    if not args.gene_expr_dir.is_dir():
        raise SystemExit(f"Directory not found: {args.gene_expr_dir}")

    print(f"Loading {args.experiment}.ttl...")
    graph = load_graph(args.gene_expr_dir, args.experiment)
    print(f"Loaded {len(graph)} triples\n")

    if args.list_contrasts:
        query = QUERY_LIST_CONTRASTS % {"experiment": args.experiment}
        print("Contrast labels and gene counts:")
        print("-" * 80)
        results = run_query(graph, query)
        for row in results:
            cid = row.contrastId or ""
            label = row.contrastLabel or "(no label)"
            count = row.geneCount or 0
            print(f"  {cid:12} | {count:5} genes | {label}")
        print(f"\nTotal: {len(results)} contrast(s)")
        return 0

    # Build contrast filter
    if args.contrast:
        # Match contrast label containing the substring (e.g. "1 hour" for aortic banding 1h vs sham 1h)
        contrast_filter = (
            'FILTER(BOUND(?contrastLabel) && '
            f'REGEX(STR(?contrastLabel), "aortic banding.*{args.contrast}.*vs.*sham.*{args.contrast}", "i"))'
        )
    else:
        contrast_filter = ""

    # Build optional fold-change and p-value filters
    extra_filters = []
    if args.min_abs_log2fc is not None:
        extra_filters.append(f"FILTER(ABS(?log2fc) >= {args.min_abs_log2fc})")
    if args.max_adj_p_value is not None:
        extra_filters.append(f"FILTER(BOUND(?adjPValue) && ?adjPValue <= {args.max_adj_p_value})")
    if extra_filters:
        contrast_filter += "\n  " + "\n  ".join(extra_filters)

    query = QUERY_BASE % {
        "experiment": args.experiment,
        "contrast_filter": contrast_filter,
        "limit": args.limit,
    }

    print("Query:")
    print("-" * 80)
    print(query.strip())
    print("-" * 80)

    results = run_query(graph, query)
    print(f"\nResults: {len(results)} row(s)")

    if args.verbose and results:
        print("\nSample (first 15):")
        for i, row in enumerate(results[:15], 1):
            sym = row.geneSymbol or "(no symbol)"
            log2fc = row.log2fc or "?"
            adjp = row.adjPValue or "?"
            label = (row.contrastLabel or "")[:50]
            print(f"  {i:2}. {sym:12} | log2fc={log2fc:8} | adjP={adjp:10} | {label}")

    if args.export_csv and results:
        with open(args.export_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["geneSymbol", "log2fc", "adjPValue", "contrastLabel"])
            for row in results:
                w.writerow([
                    str(row.geneSymbol) if row.geneSymbol else "",
                    str(row.log2fc) if row.log2fc else "",
                    str(row.adjPValue) if row.adjPValue else "",
                    str(row.contrastLabel) if row.contrastLabel else "",
                ])
        print(f"\nExported to {args.export_csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
