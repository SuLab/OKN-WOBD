#!/usr/bin/env python3
"""
Query for isoprenoid biosynthesis genes across all GXA species using UniProt annotations.

This script:
1. Gets child terms of GO:0008299 (isoprenoid biosynthetic process) from Ubergraph
2. Finds all species in GXA
3. For each species, gets genes annotated to isoprenoid GO terms from UniProt
   - Arabidopsis: uses AGI locus IDs (AT5G62360)
   - Other species: uses Ensembl gene IDs (ENSG..., ENSMUSG...)
4. Queries GXA for upregulation of those genes
5. Reports summary table by species

Usage:
    cd scripts/demos && python biosynthesis/query_isoprenoid_cross_species.py

Output:
    biosynthesis/isoprenoid_cross_species.csv
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient


# NCBI Taxonomy IDs for species
SPECIES_TAXON_MAP = {
    "Arabidopsis thaliana": "3702",
    "Homo sapiens": "9606",
    "Mus musculus": "10090",
    "Rattus norvegicus": "10116",
    "Danio rerio": "7955",
    "Drosophila melanogaster": "7227",
    "Caenorhabditis elegans": "6239",
    "Zea mays": "4577",
    "Oryza sativa": "39947",
    "Saccharomyces cerevisiae": "559292",
}


def get_isoprenoid_go_terms(client: SPARQLClient) -> Tuple[Set[str], Dict[str, str]]:
    """
    Get all child terms of 'isoprenoid biosynthetic process' (GO:0008299) from Ubergraph.
    Returns tuple of (go_ids set, go_labels dict).
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

    go_ids = {row["goId"] for row in results if row.get("goId")}
    go_labels = {row["goId"]: row.get("label", "") for row in results}

    return go_ids, go_labels


def get_gxa_species(fuseki: FusekiClient) -> List[str]:
    """Get list of species (taxon names) available in GXA."""
    print("\nStep 2: Getting species from GXA...")

    query = """
    SELECT DISTINCT ?taxon WHERE {
        ?study a biolink:Study ;
               biolink:in_taxon ?taxon .
    }
    ORDER BY ?taxon
    """

    results = fuseki.query_simple(query)
    species = [r.get("taxon") for r in results if r.get("taxon")]
    print(f"  Found {len(species)} species in GXA")

    return species


def get_genes_from_uniprot_arabidopsis(go_ids: Set[str]) -> List[Dict[str, str]]:
    """
    Get Arabidopsis genes annotated to GO terms from UniProt.
    Uses AGI locus IDs (e.g., AT5G62360) which match GXA format.
    """
    # Build VALUES clause with GO URIs (limit to avoid timeout)
    go_list = list(go_ids)[:50]  # Limit GO terms
    go_uris = " ".join(
        f'<http://purl.obolibrary.org/obo/{gid.replace(":", "_")}>'
        for gid in go_list
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
    LIMIT 500
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

            if gene:
                results.append({
                    "gene": gene.upper(),
                    "goId": go_id,
                    "gene_uri_prefix": "https://www.ncbi.nlm.nih.gov/gene/",
                })

        return results

    except Exception as e:
        print(f"    Error querying UniProt for Arabidopsis: {e}")
        return []


def get_genes_from_uniprot_ncbi(
    taxon_id: str,
    go_ids: Set[str],
    species_name: str,
) -> List[Dict[str, str]]:
    """
    Get genes annotated to GO terms from UniProt using NCBI Gene cross-references.
    Returns NCBI Gene IDs which match GXA format for human and other species.
    """
    go_list = list(go_ids)[:50]
    go_uris = " ".join(
        f'<http://purl.obolibrary.org/obo/{gid.replace(":", "_")}>'
        for gid in go_list
    )

    query = f'''
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?ncbiGene ?go WHERE {{
        VALUES ?go {{ {go_uris} }}
        ?protein a up:Protein ;
                 up:organism taxon:{taxon_id} ;
                 up:classifiedWith ?go ;
                 rdfs:seeAlso ?ncbiGene .

        # Filter for NCBI Gene (GeneID) cross-references
        FILTER(STRSTARTS(STR(?ncbiGene), "http://purl.uniprot.org/geneid/"))
    }}
    LIMIT 500
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
            gene_uri = b.get("ncbiGene", {}).get("value", "")
            go_uri = b.get("go", {}).get("value", "")
            go_id = go_uri.split("/")[-1].replace("_", ":")

            if gene_uri:
                gene_id = gene_uri.split("/")[-1]
                results.append({
                    "gene": gene_id,
                    "goId": go_id,
                    "gene_uri_prefix": "https://www.ncbi.nlm.nih.gov/gene/",
                })

        return results

    except Exception as e:
        print(f"    Error querying UniProt NCBI for {species_name}: {e}")
        return []


def get_genes_from_uniprot_ensembl(
    taxon_id: str,
    go_ids: Set[str],
    species_name: str,
    uri_prefix: str = "http://identifiers.org/ensembl/",
) -> List[Dict[str, str]]:
    """
    Get genes annotated to GO terms from UniProt using Ensembl cross-references.
    Returns Ensembl gene IDs.
    """
    go_list = list(go_ids)[:50]
    go_uris = " ".join(
        f'<http://purl.obolibrary.org/obo/{gid.replace(":", "_")}>'
        for gid in go_list
    )

    query = f'''
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?ensemblGene ?go WHERE {{
        VALUES ?go {{ {go_uris} }}
        ?protein a up:Protein ;
                 up:organism taxon:{taxon_id} ;
                 up:classifiedWith ?go ;
                 rdfs:seeAlso ?xref .

        ?xref up:database <http://purl.uniprot.org/database/Ensembl> .
        ?xref up:transcribedFrom ?ensemblGene .
    }}
    LIMIT 500
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
            gene_uri = b.get("ensemblGene", {}).get("value", "")
            go_uri = b.get("go", {}).get("value", "")
            go_id = go_uri.split("/")[-1].replace("_", ":")

            if gene_uri and "/ensembl/" in gene_uri:
                # Extract gene ID and remove version number
                gene_id = gene_uri.split("/")[-1].split(".")[0]
                if "G" in gene_id:  # Ensure it's a gene ID, not transcript
                    results.append({
                        "gene": gene_id,
                        "goId": go_id,
                        "gene_uri_prefix": uri_prefix,
                    })

        return results

    except Exception as e:
        print(f"    Error querying UniProt Ensembl for {species_name}: {e}")
        return []


def get_gene_expression(
    fuseki: FusekiClient,
    gene_ids: Set[str],
    gene_uri_prefix: str,
    taxon_filter: str,
) -> List[Dict[str, str]]:
    """
    Query GXA for expression of given genes in studies for a specific taxon.
    Returns upregulated genes (log2fc > 1, pvalue < 0.05).
    """
    if not gene_ids:
        return []

    # Build VALUES clause for gene URIs
    gene_uris = " ".join(
        f'<{gene_uri_prefix}{gid}>'
        for gid in gene_ids
    )

    query = f'''
    SELECT DISTINCT ?studyId ?studyTitle ?assayId ?geneId ?log2fc ?pvalue
    WHERE {{
        VALUES ?gene {{ {gene_uris} }}

        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        FILTER(?log2fc > 1.0)
        FILTER(?pvalue < 0.05)

        ?study biolink:has_output ?assay ;
               biolink:name ?studyId ;
               biolink:in_taxon ?taxon .
        FILTER(CONTAINS(LCASE(?taxon), LCASE("{taxon_filter}")))

        OPTIONAL {{ ?study spokegenelab:project_title ?studyTitle }}

        BIND(REPLACE(STR(?gene), ".*[/#]", "") AS ?geneId)
        BIND(REPLACE(STR(?assay), ".*[/#]", "") AS ?assayId)
    }}
    ORDER BY ?studyId DESC(?log2fc)
    LIMIT 1000
    '''

    return fuseki.query_simple(query)


def process_species(
    fuseki: FusekiClient,
    species_name: str,
    go_ids: Set[str],
) -> Dict:
    """
    Process a single species: get UniProt genes, query GXA for upregulation.
    Returns summary dict.

    Gene ID formats vary by species in GXA:
    - Arabidopsis: AGI locus IDs (AT5G62360) with NCBI prefix
    - Human: NCBI Gene IDs (numeric) with NCBI prefix
    - Mouse: Ensembl gene IDs with identifiers.org prefix
    - Zebrafish, Drosophila, etc.: Ensembl/species-specific IDs with NCBI prefix
    """
    taxon_id = SPECIES_TAXON_MAP.get(species_name)
    if not taxon_id:
        return {
            "species": species_name,
            "uniprot_genes": 0,
            "upregulated_genes": 0,
            "studies": 0,
            "assays": 0,
            "error": "Unknown taxon ID",
        }

    # Get genes from UniProt using species-appropriate method
    gene_results = []

    if species_name == "Arabidopsis thaliana":
        # Arabidopsis uses AGI locus IDs
        gene_results = get_genes_from_uniprot_arabidopsis(go_ids)
        gene_uri_prefix = "https://www.ncbi.nlm.nih.gov/gene/"

    elif species_name == "Homo sapiens":
        # Human uses NCBI Gene IDs (numeric)
        gene_results = get_genes_from_uniprot_ncbi(taxon_id, go_ids, species_name)
        gene_uri_prefix = "https://www.ncbi.nlm.nih.gov/gene/"

    elif species_name == "Mus musculus":
        # Mouse uses Ensembl IDs with identifiers.org prefix
        gene_results = get_genes_from_uniprot_ensembl(
            taxon_id, go_ids, species_name,
            uri_prefix="http://identifiers.org/ensembl/"
        )
        gene_uri_prefix = "http://identifiers.org/ensembl/"

    elif species_name in ["Danio rerio", "Drosophila melanogaster"]:
        # Zebrafish and Drosophila use Ensembl/FlyBase IDs with NCBI prefix
        gene_results = get_genes_from_uniprot_ensembl(
            taxon_id, go_ids, species_name,
            uri_prefix="https://www.ncbi.nlm.nih.gov/gene/"
        )
        gene_uri_prefix = "https://www.ncbi.nlm.nih.gov/gene/"

    else:
        # Try NCBI Gene IDs first, fall back to Ensembl
        gene_results = get_genes_from_uniprot_ncbi(taxon_id, go_ids, species_name)
        gene_uri_prefix = "https://www.ncbi.nlm.nih.gov/gene/"
        if not gene_results:
            gene_results = get_genes_from_uniprot_ensembl(
                taxon_id, go_ids, species_name,
                uri_prefix="https://www.ncbi.nlm.nih.gov/gene/"
            )

    if not gene_results:
        return {
            "species": species_name,
            "uniprot_genes": 0,
            "upregulated_genes": 0,
            "studies": 0,
            "assays": 0,
            "error": None,
        }

    gene_ids = {r["gene"] for r in gene_results}
    # Use the URI prefix from the first result
    if gene_results:
        gene_uri_prefix = gene_results[0].get("gene_uri_prefix", gene_uri_prefix)

    # Query GXA for expression
    taxon_filter = species_name.split()[0]  # Use genus name for filtering
    expression_results = get_gene_expression(
        fuseki, gene_ids, gene_uri_prefix, taxon_filter
    )

    unique_genes = {r.get("geneId") for r in expression_results if r.get("geneId")}
    unique_studies = {r.get("studyId") for r in expression_results if r.get("studyId")}
    unique_assays = {r.get("assayId") for r in expression_results if r.get("assayId")}

    return {
        "species": species_name,
        "uniprot_genes": len(gene_ids),
        "upregulated_genes": len(unique_genes),
        "studies": len(unique_studies),
        "assays": len(unique_assays),
        "error": None,
        "expression_results": expression_results,
        "gene_results": gene_results,
    }


def export_results_to_csv(
    all_results: List[Dict],
    go_labels: Dict[str, str],
    output_path: Path,
) -> None:
    """Export detailed results to CSV."""
    fieldnames = [
        "species", "study_id", "study_title", "assay_id",
        "gene_id", "go_terms", "log2fc", "adj_pvalue"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for species_result in all_results:
            species = species_result.get("species", "")
            expression_results = species_result.get("expression_results", [])
            gene_results = species_result.get("gene_results", [])

            # Build gene-GO mapping
            gene_go_map: Dict[str, Set[str]] = {}
            for r in gene_results:
                gene = r.get("gene", "")
                go_id = r.get("goId", "")
                if gene not in gene_go_map:
                    gene_go_map[gene] = set()
                if go_id:
                    gene_go_map[gene].add(go_id)

            for row in expression_results:
                gene_id = row.get("geneId", "")
                go_ids_for_gene = gene_go_map.get(gene_id, set())
                go_names = [go_labels.get(gid, "") for gid in go_ids_for_gene]

                writer.writerow({
                    "species": species,
                    "study_id": row.get("studyId", ""),
                    "study_title": row.get("studyTitle", ""),
                    "assay_id": row.get("assayId", ""),
                    "gene_id": gene_id,
                    "go_terms": "; ".join(sorted(go_ids_for_gene)),
                    "log2fc": row.get("log2fc", ""),
                    "adj_pvalue": row.get("pvalue", ""),
                })


def main():
    """Main entry point."""
    print("=" * 80)
    print("Cross-Species Isoprenoid Biosynthesis Gene Expression Analysis")
    print("=" * 80)

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
    go_ids, go_labels = get_isoprenoid_go_terms(sparql_client)
    if not go_ids:
        print("ERROR: No GO terms found.")
        sys.exit(1)

    print(f"\n  Sample GO terms:")
    for go_id in list(go_ids)[:5]:
        print(f"    - {go_id}: {go_labels.get(go_id, '')}")

    # Step 2: Get species from GXA
    gxa_species = get_gxa_species(fuseki_client)

    # Filter to species we have taxon IDs for
    target_species = [s for s in gxa_species if s in SPECIES_TAXON_MAP]
    print(f"\n  Target species (have taxon mapping): {len(target_species)}")
    for s in target_species:
        print(f"    - {s}")

    # Step 3: Process each species
    print("\nStep 3: Processing each species...")
    all_results = []

    for species in target_species:
        print(f"\n  Processing {species}...")
        result = process_species(fuseki_client, species, go_ids)
        all_results.append(result)

        print(f"    UniProt genes: {result['uniprot_genes']}")
        print(f"    Upregulated: {result['upregulated_genes']}")
        print(f"    Studies: {result['studies']}")
        if result.get("error"):
            print(f"    Error: {result['error']}")

    # Step 4: Export to CSV
    output_path = Path(__file__).parent / "isoprenoid_cross_species.csv"
    export_results_to_csv(all_results, go_labels, output_path)
    print(f"\n  Detailed results saved to: {output_path}")

    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"\n{'Species':<30} {'UniProt Genes':>14} {'Upregulated':>12} {'Studies':>10}")
    print("-" * 70)

    total_genes = 0
    total_upreg = 0
    total_studies = 0

    for r in all_results:
        print(f"{r['species']:<30} {r['uniprot_genes']:>14} {r['upregulated_genes']:>12} {r['studies']:>10}")
        total_genes += r['uniprot_genes']
        total_upreg += r['upregulated_genes']
        total_studies += r['studies']

    print("-" * 70)
    print(f"{'TOTAL':<30} {total_genes:>14} {total_upreg:>12} {total_studies:>10}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
