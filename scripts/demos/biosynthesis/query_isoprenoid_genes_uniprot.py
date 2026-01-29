#!/usr/bin/env python3
"""
Query for Arabidopsis isoprenoid biosynthesis genes using UniProt annotations.

This script finds upregulated genes even when the pathway isn't statistically enriched:
1. Gets child terms of GO:0008299 (isoprenoid biosynthetic process) from Ubergraph
2. Gets Arabidopsis genes annotated to those GO terms from UniProt
3. Queries GXA for upregulation of those genes in any Arabidopsis assay
4. Exports study id, study description, assay id, go term, gene symbol to CSV

Usage:
    cd scripts/demos && python biosynthesis/query_isoprenoid_genes_uniprot.py

Output:
    biosynthesis/isoprenoid_genes_uniprot.csv
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Set
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient


def get_isoprenoid_go_terms(client: SPARQLClient) -> List[Dict[str, str]]:
    """
    Get all child terms of 'isoprenoid biosynthetic process' (GO:0008299) from Ubergraph.
    """
    print("Step 1: Querying Ubergraph for child terms of GO:0008299...")

    query = """
    SELECT DISTINCT ?goId ?label WHERE {
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


def get_arabidopsis_genes_from_uniprot(go_ids: Set[str]) -> List[Dict[str, str]]:
    """
    Get Arabidopsis genes annotated to GO terms from UniProt SPARQL.

    Args:
        go_ids: Set of GO IDs (e.g., {"GO:0008299", "GO:0009686"})

    Returns:
        List of dicts with 'gene' (uppercase AGI locus ID) and 'goId'
    """
    print(f"\nStep 2: Querying UniProt for Arabidopsis genes...")
    print(f"  Searching {len(go_ids)} GO terms...")

    # Build VALUES clause with GO URIs
    go_uris = " ".join(
        f'<http://purl.obolibrary.org/obo/{gid.replace(":", "_")}>'
        for gid in go_ids
    )

    query = f'''
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

    SELECT DISTINCT ?gene ?go WHERE {{
        VALUES ?go {{ {go_uris} }}
        ?protein a up:Protein ;
                 up:organism taxon:3702 ;
                 up:classifiedWith ?go ;
                 up:encodedBy/up:locusName ?gene .
    }}
    '''

    try:
        resp = requests.post(
            "https://sparql.uniprot.org/sparql",
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])

        results = []
        for b in bindings:
            gene = b.get("gene", {}).get("value", "")
            go_uri = b.get("go", {}).get("value", "")
            go_id = go_uri.split("/")[-1].replace("_", ":")

            results.append({
                "gene": gene.upper(),  # Convert to uppercase to match GXA
                "goId": go_id,
            })

        print(f"  Found {len(results)} gene-GO associations")
        return results

    except Exception as e:
        print(f"  Error querying UniProt: {e}")
        return []


def get_gene_expression_in_arabidopsis(
    fuseki: FusekiClient,
    gene_symbols: Set[str],
) -> List[Dict[str, str]]:
    """
    Query GXA for expression of given genes in Arabidopsis studies.
    Returns upregulated genes regardless of pathway enrichment.
    """
    print(f"\nStep 3: Querying GXA for gene expression...")
    print(f"  Searching {len(gene_symbols)} genes in Arabidopsis studies...")

    # Build VALUES clause for gene IDs
    # GXA stores genes as URIs like https://www.ncbi.nlm.nih.gov/gene/AT5G62360
    gene_uris = " ".join(
        f'<https://www.ncbi.nlm.nih.gov/gene/{sym}>'
        for sym in gene_symbols
    )

    query = f'''
    SELECT DISTINCT ?studyId ?studyTitle ?studyDesc ?assayId ?geneSymbol ?log2fc ?pvalue
    WHERE {{
        # Match genes by URI
        VALUES ?gene {{ {gene_uris} }}

        # Find expression data
        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        # Filter for significantly upregulated
        FILTER(?log2fc > 1.0)
        FILTER(?pvalue < 0.05)

        # Get study (Arabidopsis only)
        ?study biolink:has_output ?assay ;
               biolink:name ?studyId ;
               biolink:in_taxon ?taxon .
        FILTER(?taxon = "Arabidopsis thaliana" || ?taxon = "3702")

        OPTIONAL {{ ?study spokegenelab:project_title ?studyTitle }}
        OPTIONAL {{ ?study biolink:description ?studyDesc }}

        # Extract gene symbol from URI
        BIND(REPLACE(STR(?gene), ".*[/#]", "") AS ?geneSymbol)
        BIND(REPLACE(STR(?assay), ".*[/#]", "") AS ?assayId)
    }}
    ORDER BY ?studyId DESC(?log2fc)
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} expression results")

    return results


def export_to_csv(
    results: List[Dict[str, str]],
    gene_go_map: Dict[str, Set[str]],
    go_labels: Dict[str, str],
    output_path: Path,
) -> None:
    """Export results to CSV with GO term annotations."""
    print(f"\nStep 4: Exporting to CSV...")

    fieldnames = [
        "study_id", "study_description", "assay_id",
        "gene_symbol", "go_terms", "go_term_names",
        "log2fc", "adj_pvalue"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in results:
            symbol = row.get("geneSymbol", "")
            go_ids = gene_go_map.get(symbol, set())
            go_names = [go_labels.get(gid, "") for gid in go_ids]

            study_desc = row.get("studyTitle") or row.get("studyDesc") or ""

            writer.writerow({
                "study_id": row.get("studyId", ""),
                "study_description": study_desc,
                "assay_id": row.get("assayId", ""),
                "gene_symbol": symbol,
                "go_terms": "; ".join(sorted(go_ids)),
                "go_term_names": "; ".join(sorted(filter(None, go_names))),
                "log2fc": row.get("log2fc", ""),
                "adj_pvalue": row.get("pvalue", ""),
            })

    print(f"  Exported {len(results)} rows to {output_path}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Isoprenoid Biosynthesis Genes via UniProt Annotations")
    print("(Finds genes even without pathway enrichment)")
    print("=" * 70)

    # Initialize clients
    sparql_client = SPARQLClient()
    fuseki_client = FusekiClient(dataset="GXA-v2")

    # Check Fuseki availability
    print("\nChecking Fuseki server availability...")
    if not fuseki_client.is_available():
        print("ERROR: Fuseki server is not available.")
        sys.exit(1)
    print("  Fuseki server is available!")

    # Step 1: Get GO terms
    go_terms = get_isoprenoid_go_terms(sparql_client)
    if not go_terms:
        print("ERROR: No GO terms found.")
        sys.exit(1)

    go_ids = {row["goId"] for row in go_terms if row.get("goId")}
    go_labels = {row["goId"]: row.get("label", "") for row in go_terms}

    print(f"\n  Sample GO terms:")
    for term in go_terms[:5]:
        print(f"    - {term.get('goId')}: {term.get('label')}")

    # Step 2: Get genes from UniProt
    gene_results = get_arabidopsis_genes_from_uniprot(go_ids)
    if not gene_results:
        print("No genes found in UniProt for these GO terms.")
        sys.exit(0)

    # Build gene-GO mapping
    gene_symbols = set()
    gene_go_map: Dict[str, Set[str]] = {}

    for row in gene_results:
        gene = row.get("gene", "")
        go_id = row.get("goId", "")
        if gene:
            gene_symbols.add(gene)
            if gene not in gene_go_map:
                gene_go_map[gene] = set()
            if go_id:
                gene_go_map[gene].add(go_id)

    print(f"\n  Sample genes from UniProt:")
    for row in gene_results[:5]:
        print(f"    - {row.get('gene')}: {row.get('goId')}")
    print(f"\n  Unique genes: {len(gene_symbols)}")

    # Step 3: Query GXA for expression
    expression_results = get_gene_expression_in_arabidopsis(fuseki_client, gene_symbols)

    if not expression_results:
        print("No expression results found in GXA.")
        sys.exit(0)

    # Step 4: Export to CSV
    output_path = Path(__file__).parent / "isoprenoid_genes_uniprot.csv"
    export_to_csv(expression_results, gene_go_map, go_labels, output_path)

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    unique_studies = {row.get("studyId") for row in expression_results}
    unique_assays = {row.get("assayId") for row in expression_results}
    unique_genes = {row.get("geneSymbol") for row in expression_results}
    go_terms_found = set()
    for gene in unique_genes:
        go_terms_found.update(gene_go_map.get(gene, set()))

    print(f"  UniProt genes queried: {len(gene_symbols)}")
    print(f"  Genes found upregulated: {len(unique_genes)}")
    print(f"  Unique studies: {len(unique_studies)}")
    print(f"  Unique assays: {len(unique_assays)}")
    print(f"  GO terms represented: {len(go_terms_found)}")

    print("\n  Top 10 results (by log2fc):")
    sorted_results = sorted(
        expression_results,
        key=lambda x: float(x.get("log2fc", 0)),
        reverse=True
    )
    for i, row in enumerate(sorted_results[:10], 1):
        study = row.get("studyId", "N/A")
        gene = row.get("geneSymbol", "N/A")
        log2fc = row.get("log2fc", "N/A")
        go_ids = gene_go_map.get(gene, set())
        go_str = list(go_ids)[0] if go_ids else "N/A"
        print(f"    {i}. {study}: {gene} ({go_str}) log2fc={log2fc}")

    print(f"\n  Results saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
