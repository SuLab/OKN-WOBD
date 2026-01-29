#!/usr/bin/env python3
"""
Query for GXA assays with isoprenoid biosynthetic process GO term enrichments.

This script:
1. Finds child terms of 'isoprenoid biosynthetic process' (GO:0008299) from Ubergraph
2. Queries local GXA RDF (via Fuseki) for assays enriched for those terms
3. Exports study ID, title, assay, and enriched term to CSV

Usage:
    cd scripts/demos && python biosynthesis/query_biosynthesis_enrichments.py

Output:
    biosynthesis/isoprenoid_biosynthesis_enrichments.csv
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient


def get_biosynthesis_child_terms(client: SPARQLClient) -> List[Dict[str, str]]:
    """
    Get all child terms of 'isoprenoid biosynthetic process' (GO:0008299) from Ubergraph.

    Returns:
        List of dicts with 'uri' and 'label' keys
    """
    print("Step 1: Querying Ubergraph for child terms of GO:0008299 (isoprenoid biosynthetic process)...")

    # Query for subclasses using transitive closure (includes all descendants)
    query = """
    SELECT DISTINCT ?subclass ?label ?goId WHERE {
        ?subclass rdfs:subClassOf* obo:GO_0008299 .
        ?subclass a owl:Class .
        ?subclass rdfs:label ?label .

        # Extract GO ID from URI (e.g., GO_0009058 -> GO:0009058)
        BIND(REPLACE(STR(?subclass), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?goId)
        FILTER(STRSTARTS(STR(?subclass), "http://purl.obolibrary.org/obo/GO_"))
    }
    ORDER BY ?label
    """

    results = client.query_simple(query, endpoint="ubergraph")
    print(f"  Found {len(results)} child terms of isoprenoid biosynthetic process")

    return results


def query_gxa_enrichments(fuseki: FusekiClient, go_ids: Set[str]) -> List[Dict[str, str]]:
    """
    Query local GXA RDF for assays enriched for any of the given GO terms.

    Args:
        fuseki: FusekiClient instance
        go_ids: Set of GO IDs to search for (e.g., {"GO:0009058", "GO:0006412"})

    Returns:
        List of dicts with study_id, study_title, assay, go_id, go_term_name, pvalue
    """
    print(f"\nStep 2: Querying local GXA RDF for enrichments...")
    print(f"  Searching for {len(go_ids)} GO terms...")

    # Build VALUES clause for GO IDs
    values_clause = " ".join(f'"{go_id}"' for go_id in go_ids)

    query = f'''
    SELECT DISTINCT ?studyId ?studyTitle ?assay ?goId ?goTermName ?pvalue
    WHERE {{
        # Find enrichment linked to a GO term
        ?enrichment biolink:participates_in ?goTerm ;
                    spokegenelab:adj_p_value ?pvalue .

        # Note: in GXA data, biolink:name contains GO ID, biolink:id contains term name
        ?goTerm biolink:name ?goId .

        VALUES ?goId {{ {values_clause} }}

        OPTIONAL {{ ?goTerm biolink:id ?goTermName }}

        ?assay biolink:has_output ?enrichment .
        ?study biolink:has_output ?assay ;
               biolink:name ?studyTitle .

        # Extract study ID from URI
        BIND(REPLACE(STR(?study), ".*[/#]", "") AS ?studyId)
    }}
    ORDER BY ?pvalue
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} enrichment results")

    return results


def extract_study_id(study_uri: str) -> str:
    """Extract study ID from URI."""
    # Handle URIs like https://example.org/study/E-MTAB-123
    if "/" in study_uri:
        return study_uri.split("/")[-1]
    return study_uri


def export_to_csv(results: List[Dict[str, str]], output_path: Path) -> None:
    """
    Export results to CSV file.

    Args:
        results: List of enrichment result dicts
        output_path: Path to output CSV file
    """
    print(f"\nStep 3: Exporting to CSV...")

    fieldnames = ["study_id", "study_title", "assay", "go_id", "go_term_name", "adj_pvalue"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in results:
            writer.writerow({
                "study_id": row.get("studyId", ""),
                "study_title": row.get("studyTitle", ""),
                "assay": row.get("assay", ""),
                "go_id": row.get("goId", ""),
                "go_term_name": row.get("goTermName", ""),
                "adj_pvalue": row.get("pvalue", ""),
            })

    print(f"  Exported {len(results)} rows to {output_path}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Isoprenoid Biosynthetic Process GO Term Enrichment Query")
    print("=" * 70)

    # Initialize clients
    sparql_client = SPARQLClient()
    fuseki_client = FusekiClient(dataset="GXA-v2")

    # Check Fuseki availability
    print("\nChecking Fuseki server availability...")
    if not fuseki_client.is_available():
        print("ERROR: Fuseki server is not available at the configured endpoint.")
        print(f"Please ensure Fuseki is running at http://{fuseki_client.host}:{fuseki_client.port}")
        print(f"with dataset '{fuseki_client.dataset}'")
        sys.exit(1)
    print("  Fuseki server is available!")

    # Step 1: Get child terms of biosynthetic process from Ubergraph
    child_terms = get_biosynthesis_child_terms(sparql_client)

    if not child_terms:
        print("ERROR: No child terms found. Check Ubergraph connectivity.")
        sys.exit(1)

    # Extract GO IDs
    go_ids = {row["goId"] for row in child_terms if row.get("goId")}
    print(f"\n  Sample GO terms found:")
    for term in child_terms[:5]:
        print(f"    - {term.get('goId', 'N/A')}: {term.get('label', 'N/A')}")
    if len(child_terms) > 5:
        print(f"    ... and {len(child_terms) - 5} more")

    # Step 2: Query GXA for enrichments
    enrichments = query_gxa_enrichments(fuseki_client, go_ids)

    if not enrichments:
        print("No enrichments found for isoprenoid biosynthetic process terms in GXA data.")
        sys.exit(0)

    # Step 3: Export to CSV
    output_path = Path(__file__).parent / "isoprenoid_biosynthesis_enrichments.csv"
    export_to_csv(enrichments, output_path)

    # Print summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    # Count unique studies and GO terms
    unique_studies = {row.get("studyId") for row in enrichments}
    unique_go_terms = {row.get("goId") for row in enrichments}

    print(f"  Total enrichments: {len(enrichments)}")
    print(f"  Unique studies: {len(unique_studies)}")
    print(f"  Unique GO terms found: {len(unique_go_terms)}")

    print("\n  Top 10 results (by p-value):")
    for i, row in enumerate(enrichments[:10], 1):
        study = row.get("studyId", "N/A")
        go_id = row.get("goId", "N/A")
        go_name = row.get("goTermName", "N/A")
        pvalue = row.get("pvalue", "N/A")
        print(f"    {i}. {study}: {go_id} ({go_name}) - p={pvalue}")

    print(f"\n  Results saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
