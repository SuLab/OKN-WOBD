#!/usr/bin/env python3
"""
Query the FRINK NDE SPARQL endpoint for influenza-related datasets.

Use this to check whether NDE contains datasets that mention "influenza" or "flu"
in name/description, and whether any have identifiers (e.g. GSE IDs) for the
NDE↔GXA bridge.

Usage:
  python scripts/query_nde_influenza.py
  python scripts/query_nde_influenza.py --sample 20   # also list sample dataset names
  python scripts/query_nde_influenza.py --gse-check   # count NDE datasets with GSE identifier (NDE↔GXA linkable)
  python scripts/query_nde_influenza.py --app-query  # run app-style influenza query (with FROM nde) to debug 0 results
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

NDE_SPARQL = "https://frink.apps.renci.org/nde/sparql"


def run_sparql(query: str, endpoint: str = NDE_SPARQL) -> dict:
    """POST a SPARQL query and return JSON results."""
    req = Request(
        endpoint,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        print(f"Request failed: {e}", file=sys.stderr)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Also run a sample query listing up to N dataset names (0 = skip)",
    )
    parser.add_argument(
        "--endpoint",
        default=NDE_SPARQL,
        help="NDE SPARQL endpoint URL",
    )
    parser.add_argument(
        "--gse-check",
        action="store_true",
        help="Count NDE datasets whose identifier contains GSE (linkable to GXA)",
    )
    parser.add_argument(
        "--app-query",
        action="store_true",
        help="Run app-style influenza query (FROM nde + OPTIONAL disease/organism + REGEX) to debug 0 results",
    )
    args = parser.parse_args()

    # 0) GSE check: do any NDE datasets have identifier containing GSE (so NDE↔GXA bridge can attach data)?
    if args.gse_check:
        q_gse = """
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?identifier
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:identifier ?identifier }
  FILTER(BOUND(?identifier) && REGEX(STR(?identifier), "GSE\\\\d+", "i"))
}
LIMIT 50
"""
        print("Querying NDE for datasets with GSE in identifier (NDE↔GXA linkable)...")
        try:
            out = run_sparql(q_gse, args.endpoint)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1
        bindings = out.get("results", {}).get("bindings", [])
        print(f"Found {len(bindings)} dataset(s) with GSE identifier.\n")
        if bindings:
            for i, row in enumerate(bindings[:10], 1):
                print(f"  {i}. {row.get('name', {}).get('value', '')}  | {row.get('identifier', {}).get('value', '')}")
            if len(bindings) > 10:
                print(f"  ... and {len(bindings) - 10} more")
        else:
            print("  None. NDE↔GXA bridge will have no GSE rows to attach GXA data to for this source.")
        return 0

    # 0b) App-style query: same shape as the app (FROM nde + OPTIONALs + FILTER with REGEX on name/description)
    if args.app_query:
        q_app = """
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?identifier ?diseaseName ?organismName
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  OPTIONAL {
    ?dataset schema:healthCondition ?disease .
    ?disease schema:name ?diseaseName .
    FILTER(CONTAINS(LCASE(COALESCE(?diseaseName, "")), "influenza"))
  }
  OPTIONAL {
    { ?dataset schema:infectiousAgent ?organism . ?organism schema:name ?organismName . }
    UNION
    { ?dataset schema:species ?organism . ?organism schema:name ?organismName . }
    FILTER(CONTAINS(LCASE(COALESCE(?organismName, "")), "influenza"))
  }
  FILTER(
    REGEX(STR(?name), "influenza", "i") || REGEX(STR(COALESCE(?description, "")), "influenza", "i")
    || REGEX(STR(?name), "flu", "i") || REGEX(STR(COALESCE(?description, "")), "flu", "i")
  )
}
LIMIT 50
"""
        print("Running app-style influenza query (WITH FROM nde) against NDE endpoint...")
        try:
            out = run_sparql(q_app, args.endpoint)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1
        bindings = out.get("results", {}).get("bindings", [])
        print(f"Row count: {len(bindings)}")
        if bindings:
            print("First row name:", bindings[0].get("name", {}).get("value", "")[:80])
        else:
            print("(0 results – app may be sending this shape to NDE; if so, NDE returns 0 for this query.)")
        return 0

    # 1) Datasets with "influenza" or "flu" in name or description
    q_influenza = """
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?identifier
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  FILTER(
    REGEX(STR(?name), "influenza|flu", "i")
    || REGEX(STR(COALESCE(?description, "")), "influenza|flu", "i")
  )
}
LIMIT 100
"""
    print("Querying NDE for datasets with 'influenza' or 'flu' in name/description...")
    try:
        out = run_sparql(q_influenza, args.endpoint)
    except Exception:
        return 1
    bindings = out.get("results", {}).get("bindings", [])
    print(f"Found {len(bindings)} dataset(s).\n")
    if bindings:
        for i, row in enumerate(bindings, 1):
            name = row.get("name", {}).get("value", "")
            desc = row.get("description", {}).get("value", "")[:120]
            ident = row.get("identifier", {}).get("value", "")
            print(f"  {i}. name: {name}")
            if ident:
                print(f"     identifier: {ident}")
            if desc:
                print(f"     description: {desc}...")
            print()
    else:
        print("  (No datasets matched. NDE may not contain influenza/flu in name or description.)")

    # 2) Optional: sample of all datasets (name + identifier) to see coverage
    if args.sample > 0:
        q_sample = """
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?name ?identifier
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:identifier ?identifier }
}
LIMIT """ + str(args.sample)
        print(f"Sample of up to {args.sample} dataset name(s) and identifier(s)...")
        try:
            out = run_sparql(q_sample, args.endpoint)
        except Exception:
            return 1
        bindings = out.get("results", {}).get("bindings", [])
        for row in bindings:
            name = row.get("name", {}).get("value", "")
            ident = row.get("identifier", {}).get("value", "")
            print(f"  {name}" + (f"  | identifier: {ident}" if ident else ""))
        print(f"\nTotal shown: {len(bindings)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
