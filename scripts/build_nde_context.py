#!/usr/bin/env python3
"""
Build an NDE context JSON file from a SPARQL endpoint.

This queries an NDE graph (e.g. NDE-in-FRINK) to extract:
- Top classes by instance count
- Top properties on schema:Dataset
- Example triples for selected properties
- A map of commonly used namespace prefixes

and writes a compact JSON summary to web/context/nde_global.json.

Usage (from repo root):

    python scripts/build_nde_context.py \\
      --endpoint https://frink.apps.renci.org/nde/sparql

You can also override the output path with --output.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests


DEFAULT_ENDPOINT = "https://frink.apps.renci.org/nde/sparql"
DEFAULT_OUTPUT = Path("web/context/nde_global.json")

PREFIXES = """PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


@dataclass
class Args:
    endpoint: str
    output: Path
    timeout: int


def parse_args(argv: Iterable[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"SPARQL endpoint URL (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON file to write context (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds for SPARQL requests (default: 60)",
    )
    ns = parser.parse_args(argv)
    return Args(endpoint=ns.endpoint, output=ns.output, timeout=ns.timeout)


def run_sparql(endpoint: str, query: str, timeout: int) -> Dict[str, Any]:
    resp = requests.post(
        endpoint,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def get_top_classes(args: Args, limit: int = 50) -> List[Dict[str, Any]]:
    query = f"""{PREFIXES}
SELECT ?class (COUNT(DISTINCT ?s) AS ?count)
WHERE {{
  ?s rdf:type ?class .
}}
GROUP BY ?class
ORDER BY DESC(?count)
LIMIT {limit}
"""
    data = run_sparql(args.endpoint, query, args.timeout)
    rows: List[Dict[str, Any]] = []
    for binding in data.get("results", {}).get("bindings", []):
        class_iri = binding.get("class", {}).get("value")
        count_str = binding.get("count", {}).get("value")
        if not class_iri or count_str is None:
            continue
        try:
            count = int(count_str)
        except ValueError:
            continue
        rows.append({"iri": class_iri, "count": count})
    return rows


def get_dataset_properties(args: Args, limit: int = 50) -> List[Dict[str, Any]]:
    query = f"""{PREFIXES}
SELECT ?p (COUNT(*) AS ?count)
WHERE {{
  ?s rdf:type schema:Dataset ;
     ?p ?o .
}}
GROUP BY ?p
ORDER BY DESC(?count)
LIMIT {limit}
"""
    data = run_sparql(args.endpoint, query, args.timeout)
    props: List[Dict[str, Any]] = []
    for binding in data.get("results", {}).get("bindings", []):
        pred = binding.get("p", {}).get("value")
        count_str = binding.get("count", {}).get("value")
        if not pred or count_str is None:
            continue
        try:
            count = int(count_str)
        except ValueError:
            continue
        props.append({"iri": pred, "count": count})
    return props


def get_example_triples(
    args: Args,
    predicate_iri: str,
    limit: int = 20,
) -> List[Dict[str, str]]:
    """
    Fetch example triples on schema:Dataset for a given predicate.
    """

    query = f"""{PREFIXES}
SELECT ?s ?o
WHERE {{
  ?s rdf:type schema:Dataset ;
     <{predicate_iri}> ?o .
}}
LIMIT {limit}
"""
    data = run_sparql(args.endpoint, query, args.timeout)
    examples: List[Dict[str, str]] = []
    for binding in data.get("results", {}).get("bindings", []):
        s = binding.get("s", {}).get("value")
        o = binding.get("o", {}).get("value")
        if not s or o is None:
            continue
        examples.append({"subject": s, "object": o})
    return examples


def build_context(args: Args) -> Dict[str, Any]:
    classes = get_top_classes(args, limit=50)
    dataset_props = get_dataset_properties(args, limit=50)

    # For a few key properties, grab example triples.
    KEY_PROPS = {
        "schema:infectiousAgent": "http://schema.org/infectiousAgent",
        "schema:includedInDataCatalog": "http://schema.org/includedInDataCatalog",
        "schema:name": "http://schema.org/name",
    }

    props_with_examples: Dict[str, Any] = {}
    namespaces: Dict[str, int] = defaultdict(int)

    for prop in dataset_props:
        iri = prop["iri"]
        entry: Dict[str, Any] = {"iri": iri, "count": prop["count"]}

        # Track namespace portion of the IRI for prefix derivation.
        sep_index = max(iri.rfind("#"), iri.rfind("/"))
        if sep_index != -1:
            ns = iri[: sep_index + 1]
            namespaces[ns] += 1

        # If this predicate is one of the key ones, add example triples.
        for curie, full_iri in KEY_PROPS.items():
            if iri == full_iri:
                entry["curie"] = curie
                entry["examples"] = get_example_triples(args, iri, limit=20)
                break

        props_with_examples[iri] = entry

    # Derive a simple prefix map from observed namespaces, seeding with
    # well-known vocabulary prefixes.
    base_prefixes: Dict[str, str] = {
        "schema": "http://schema.org/",
        "rdf": "http://www.w3.org/1999/02/22/rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "dcterms": "http://purl.org/dc/terms/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    prefixes: Dict[str, str] = {}

    # First add any known namespaces we actually observed.
    for prefix, ns in base_prefixes.items():
        if ns in namespaces:
            prefixes[prefix] = ns
            namespaces.pop(ns, None)

    # For any remaining namespaces, assign synthetic prefixes (ns1, ns2, ...).
    counter = 1
    for ns, _ in sorted(namespaces.items(), key=lambda kv: (-kv[1], kv[0])):
        key = f"ns{counter}"
        prefixes[key] = ns
        counter += 1

    return {
        "endpoint": args.endpoint,
        "prefixes": prefixes,
        "classes": classes,
        "dataset_properties": props_with_examples,
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    ctx = build_context(args)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ctx, indent=2), encoding="utf-8")

    print(f"Context written to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

