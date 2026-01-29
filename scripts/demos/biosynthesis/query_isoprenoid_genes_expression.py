#!/usr/bin/env python3
"""
Query for genes upregulated in assays enriched for isoprenoid biosynthesis.

This script:
1. Gets child terms of 'isoprenoid biosynthetic process' (GO:0008299) from Ubergraph
2. Finds assays in GXA enriched for those GO terms
3. Gets upregulated genes from those assays (Arabidopsis studies only)
4. Exports study id, study description, assay id, go term, gene symbol to CSV

Usage:
    cd scripts/demos && python biosynthesis/query_isoprenoid_genes_expression.py

Output:
    biosynthesis/isoprenoid_genes_upregulated.csv
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient


def get_isoprenoid_go_terms(client: SPARQLClient) -> List[Dict[str, str]]:
    """
    Get all child terms of 'isoprenoid biosynthetic process' (GO:0008299) from Ubergraph.

    Returns:
        List of dicts with 'goId' and 'label' keys
    """
    print("Step 1: Querying Ubergraph for child terms of GO:0008299...")

    query = """
    SELECT DISTINCT ?subclass ?label ?goId WHERE {
        ?subclass rdfs:subClassOf* obo:GO_0008299 .
        ?subclass a owl:Class .
        ?subclass rdfs:label ?label .
        BIND(REPLACE(STR(?subclass), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?goId)
        FILTER(STRSTARTS(STR(?subclass), "http://purl.obolibrary.org/obo/GO_"))
    }
    ORDER BY ?label
    """

    results = client.query_simple(query, endpoint="ubergraph")
    print(f"  Found {len(results)} GO terms")

    return results


def get_enriched_assays_with_upregulated_genes(
    fuseki: FusekiClient,
    go_ids: Set[str],
) -> List[Dict[str, str]]:
    """
    Query GXA for assays enriched for given GO terms AND their upregulated genes.
    Limited to Arabidopsis thaliana studies.

    Args:
        fuseki: FusekiClient instance
        go_ids: Set of GO IDs to search for

    Returns:
        List of dicts with study/assay/gene/GO information
    """
    print(f"\nStep 2: Querying GXA for enriched assays and upregulated genes...")
    print(f"  Searching for {len(go_ids)} GO terms in Arabidopsis studies...")

    # Build VALUES clause for GO IDs
    values_clause = " ".join(f'"{go_id}"' for go_id in go_ids)

    query = f'''
    SELECT DISTINCT ?studyId ?studyTitle ?studyDesc ?assayId ?goId ?goTermName ?geneSymbol ?log2fc ?pvalue
    WHERE {{
        # Find enrichment for our GO terms
        ?enrichment biolink:participates_in ?goTerm ;
                    spokegenelab:adj_p_value ?enrichPvalue .
        FILTER(?enrichPvalue < 0.05)

        # Match GO term ID
        ?goTerm biolink:name ?goId .
        VALUES ?goId {{ {values_clause} }}
        OPTIONAL {{ ?goTerm biolink:id ?goTermName }}

        # Get the assay
        ?assay biolink:has_output ?enrichment .

        # Get the study (filter for Arabidopsis)
        ?study biolink:has_output ?assay ;
               biolink:name ?studyId ;
               biolink:in_taxon ?taxon .
        FILTER(?taxon = "Arabidopsis thaliana" || ?taxon = "3702")

        OPTIONAL {{ ?study spokegenelab:project_title ?studyTitle }}
        OPTIONAL {{ ?study biolink:description ?studyDesc }}

        # Get upregulated genes from the same assay
        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        # Filter for significantly upregulated
        FILTER(?log2fc > 1.0)
        FILTER(?pvalue < 0.05)

        # Get gene symbol or extract ID from URI (for Arabidopsis AGI locus IDs)
        OPTIONAL {{ ?gene biolink:symbol ?symbol }}
        BIND(COALESCE(?symbol, REPLACE(STR(?gene), ".*[/#]", "")) AS ?geneSymbol)

        BIND(REPLACE(STR(?assay), ".*[/#]", "") AS ?assayId)
    }}
    ORDER BY ?studyId ?goId DESC(?log2fc)
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} results")

    return results


def export_to_csv(results: List[Dict[str, str]], output_path: Path) -> None:
    """
    Export results to CSV file.
    """
    print(f"\nStep 3: Exporting to CSV...")

    fieldnames = ["study_id", "study_description", "assay_id", "go_term", "go_term_name", "gene_symbol", "log2fc", "adj_pvalue"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in results:
            study_desc = row.get("studyTitle") or row.get("studyDesc") or ""

            writer.writerow({
                "study_id": row.get("studyId", ""),
                "study_description": study_desc,
                "assay_id": row.get("assayId", ""),
                "go_term": row.get("goId", ""),
                "go_term_name": row.get("goTermName", ""),
                "gene_symbol": row.get("geneSymbol", ""),
                "log2fc": row.get("log2fc", ""),
                "adj_pvalue": row.get("pvalue", ""),
            })

    print(f"  Exported {len(results)} rows to {output_path}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Isoprenoid Biosynthesis - Enriched Assays & Upregulated Genes")
    print("(Arabidopsis thaliana studies)")
    print("=" * 70)

    # Initialize clients
    sparql_client = SPARQLClient()
    fuseki_client = FusekiClient(dataset="GXA-v2")

    # Check Fuseki availability
    print("\nChecking Fuseki server availability...")
    if not fuseki_client.is_available():
        print("ERROR: Fuseki server is not available.")
        print(f"Please ensure Fuseki is running at http://{fuseki_client.host}:{fuseki_client.port}")
        sys.exit(1)
    print("  Fuseki server is available!")

    # Step 1: Get GO terms for isoprenoid biosynthesis
    go_terms = get_isoprenoid_go_terms(sparql_client)

    if not go_terms:
        print("ERROR: No GO terms found.")
        sys.exit(1)

    go_ids = {row["goId"] for row in go_terms if row.get("goId")}

    # Build GO ID to label map
    go_labels = {row["goId"]: row.get("label", "") for row in go_terms if row.get("goId")}

    print(f"\n  Sample GO terms:")
    for term in go_terms[:5]:
        print(f"    - {term.get('goId', 'N/A')}: {term.get('label', 'N/A')}")

    # Step 2: Query GXA for enriched assays and upregulated genes
    results = get_enriched_assays_with_upregulated_genes(fuseki_client, go_ids)

    if not results:
        print("No results found in GXA data for Arabidopsis studies.")
        sys.exit(0)

    # Step 3: Export to CSV
    output_path = Path(__file__).parent / "isoprenoid_genes_upregulated.csv"
    export_to_csv(results, output_path)

    # Print summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    unique_studies = {row.get("studyId") for row in results}
    unique_assays = {row.get("assayId") for row in results}
    unique_genes = {row.get("geneSymbol") for row in results}
    unique_go = {row.get("goId") for row in results}

    print(f"  Total results: {len(results)}")
    print(f"  Unique studies: {len(unique_studies)}")
    print(f"  Unique assays: {len(unique_assays)}")
    print(f"  Unique genes: {len(unique_genes)}")
    print(f"  GO terms with enrichment: {len(unique_go)}")

    print("\n  Top 10 results (by log2fc):")
    sorted_results = sorted(results, key=lambda x: float(x.get("log2fc", 0)), reverse=True)
    for i, row in enumerate(sorted_results[:10], 1):
        study = row.get("studyId", "N/A")
        gene = row.get("geneSymbol", "N/A")
        go_id = row.get("goId", "N/A")
        log2fc = row.get("log2fc", "N/A")
        print(f"    {i}. {study}: {gene} ({go_id}) log2fc={log2fc}")

    print(f"\n  Results saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
