#!/usr/bin/env python3
"""
Demo: Searching for vaccine-related datasets in the NIAID Data Ecosystem.

This script demonstrates various query patterns using the NIAIDClient.
"""

from clients import NIAIDClient, COMMON_SPECIES, COMMON_DISEASES


def main():
    """Run the vaccine search demo."""
    print("=" * 80)
    print("NIAID Data Ecosystem - Vaccine Dataset Search Demo")
    print("=" * 80)
    print()

    client = NIAIDClient()

    # 1. Simple keyword search
    print("1. SIMPLE KEYWORD SEARCH")
    print("-" * 40)
    print("Query: vaccine")

    result = client.search("vaccine", size=3)
    print(f"Total datasets found: {result.total}")
    for hit in result:
        print(f"  - {hit.get('name', 'Untitled')[:70]}")

    # 2. Field-specific query: disease
    print()
    print("2. FIELD-SPECIFIC QUERY: By Disease Name")
    print("-" * 40)
    print('Query: healthCondition.name:"influenza"')

    result = client.search_by_disease("influenza", size=3)
    print(f"Total datasets found: {result.total}")
    for hit in result:
        print(f"  - {hit.get('name', 'Untitled')[:70]}")

    # 3. Query by species using taxonomy ID
    print()
    print("3. ONTOLOGY QUERY: By Species (NCBI Taxonomy ID)")
    print("-" * 40)
    print(f'Query: species.identifier:"{COMMON_SPECIES["human"]}" (Homo sapiens)')

    result = client.search_by_species(COMMON_SPECIES["human"], size=3)
    print(f"Total datasets found: {result.total}")
    for hit in result:
        print(f"  - {hit.get('name', 'Untitled')[:70]}")

    # 4. Combined query: keyword + disease
    print()
    print("4. COMBINED QUERY: Keyword + Disease")
    print("-" * 40)
    print('Query: vaccine AND healthCondition.name:"malaria"')

    result = client.search_by_disease("malaria", keywords="vaccine", size=3)
    print(f"Total datasets found: {result.total}")
    for hit in result:
        print(f"  - {hit.get('name', 'Untitled')[:70]}")

    # 5. Combined query: keyword + species
    print()
    print("5. COMBINED QUERY: Keyword + Species")
    print("-" * 40)
    print(f'Query: vaccine AND species.identifier:"{COMMON_SPECIES["mouse"]}" (mouse)')

    result = client.search_by_species(COMMON_SPECIES["mouse"], keywords="vaccine", size=3)
    print(f"Total datasets found: {result.total}")
    for hit in result:
        print(f"  - {hit.get('name', 'Untitled')[:70]}")

    # 6. Filter by data catalog
    print()
    print("6. REPOSITORY FILTER: ImmPort Only")
    print("-" * 40)
    print("Query: vaccine (filtered to ImmPort)")

    result = client.search_by_catalog("ImmPort", query="vaccine", size=3)
    print(f"Total datasets found: {result.total}")
    for hit in result:
        print(f"  - {hit.get('name', 'Untitled')[:70]}")

    # 7. Show ontology annotations in results
    print()
    print("7. DETAILED VIEW: With Ontology Annotations")
    print("-" * 40)

    result = client.search_by_disease("influenza", keywords="vaccine", size=1)
    if result.hits:
        print(client.format_dataset(result[0], include_ontology=True))

    # 8. Facet analysis
    print()
    print("8. FACET ANALYSIS: Top Sources for Vaccine Data")
    print("-" * 40)

    result = client.search("vaccine", facet_size=10)
    catalogs = result.get_facet_values("includedInDataCatalog.name")
    for facet in catalogs[:7]:
        print(f"  {facet['term']}: {facet['count']:,} datasets")

    # Query syntax reference
    print()
    print("=" * 80)
    print("QUERY SYNTAX REFERENCE")
    print("-" * 40)
    print("""
Field-specific queries (use quotes for multi-word values):
  healthCondition.name:"COVID-19"    - Search by disease name
  species.name:"Homo sapiens"        - Search by species name
  species.identifier:"9606"          - Search by NCBI Taxonomy ID
  infectiousAgent.name:"SARS-CoV-2"  - Search by pathogen name
  includedInDataCatalog.name:"Vivli" - Search by repository

Boolean operators:
  vaccine AND influenza              - Both terms required
  vaccine OR immunization            - Either term
  (flu OR influenza) AND vaccine     - Grouping

Common NCBI Taxonomy IDs:
  9606  = Homo sapiens (human)
  10090 = Mus musculus (mouse)
  10116 = Rattus norvegicus (rat)
  9544  = Macaca mulatta (rhesus macaque)

Common MONDO Disease IDs:
  0005550 = infectious disease
  0005812 = influenza
  0005136 = malaria
  0100096 = COVID-19
""")
    print("=" * 80)


if __name__ == "__main__":
    main()
