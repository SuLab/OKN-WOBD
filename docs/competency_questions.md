# OKN-WOBD Competency Questions

This document contains competency questions (CQs) for the OKN-WOBD knowledge graph, which represents datasets from the NIAID Data Ecosystem (NDE) including ImmPort, VDJServer, Vivli, RADx Data Hub, and Project Tycho.

Each competency question is written in natural language and includes a corresponding SPARQL query that answers the question.

## Dataset Discovery Questions

### CQ1: How many datasets are available from ImmPort?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT (COUNT(DISTINCT ?dataset) AS ?count)
WHERE {
    ?dataset rdf:type schema:Dataset .
    FILTER(REGEX(STR(?dataset), "^https://okn\\.wobd\\.org/dataset/immport/"))
}
```

### CQ2: What datasets are available for influenza research?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?diseaseName
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:healthCondition ?disease .
    ?disease schema:name ?diseaseName .
    FILTER(
        ?disease = <http://purl.obolibrary.org/obo/MONDO_0005812> ||
        CONTAINS(LCASE(?diseaseName), "influenza")
    )
}
ORDER BY ?datasetName
```

**Note:** This query matches datasets by either the MONDO ontology CURIE for influenza (`MONDO:0005812`) or by string matching on the disease name. If you need a different influenza CURIE, replace `MONDO:0005812` with the appropriate identifier.

### CQ3: Find all datasets that use mouse as a model organism
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?speciesName
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:species ?species .
    ?species schema:name ?speciesName .
    FILTER(
        ?species = <https://www.uniprot.org/taxonomy/10090> ||
        REGEX(LCASE(?speciesName), "mouse|mus musculus")
    )
}
ORDER BY ?datasetName
```

**Note:** This query matches datasets by either the UniProt taxonomy CURIE for mouse (`10090`) or by string matching on the species name.

### CQ4: What datasets are related to COVID-19?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?resource
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:healthCondition <http://purl.obolibrary.org/obo/MONDO_0100096> .
    BIND(REPLACE(STR(?dataset), "https://okn.wobd.org/dataset/([^/]+)/.*", "$1") AS ?resource)
}
ORDER BY ?resource ?datasetName
```

### CQ5: List all datasets with their DOIs
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?doi
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:sameAs ?doi .
    FILTER(REGEX(STR(?doi), "^https://doi\\.org/"))
}
ORDER BY ?datasetName
LIMIT 50
```

## Funding and Organization Questions

### CQ6: Which datasets are funded by NIAID?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?grantName
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:funding ?grant .
    ?grant schema:funder <https://ror.org/043z4tv69> ;
           schema:name ?grantName .
}
ORDER BY ?datasetName
```

### CQ7: How many unique funding organizations are represented across all datasets?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT (COUNT(DISTINCT ?funder) AS ?uniqueFunders)
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:funding ?grant .
    ?grant schema:funder ?funder .
}
```

### CQ8: Find all datasets authored by researchers from Stanford University
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?authorName ?affiliation
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:author ?author .
    ?author schema:name ?authorName ;
            schema:affiliation ?org .
    ?org schema:name ?affiliation .
    FILTER(
        # Match by ROR CURIE for Stanford OR by name
        ?org = <https://ror.org/00f54p054> ||
        CONTAINS(LCASE(?affiliation), "stanford")
    )
}
ORDER BY ?datasetName
```

**Note:** This query matches datasets by either the ROR identifier for Stanford University (`https://ror.org/00f54p054`) or by string matching on the affiliation name.

## Disease and Infectious Agent Questions

### CQ9: What infectious agents are studied across all datasets?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?agent ?agentName (COUNT(?dataset) AS ?datasetCount)
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:infectiousAgent ?agent .
    ?agent schema:name ?agentName .
}
GROUP BY ?agent ?agentName
ORDER BY DESC(?datasetCount)
LIMIT 20
```

### CQ10: Which datasets study both influenza and use human subjects?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:healthCondition ?disease ;
             schema:species ?species .
    ?disease schema:name ?diseaseName .
    ?species schema:name ?speciesName .
    FILTER(
        # Match influenza by CURIE OR name
        ?disease = <http://purl.obolibrary.org/obo/MONDO_0005812> ||
        CONTAINS(LCASE(?diseaseName), "influenza")
    )
    FILTER(
        # Match human by UniProt taxonomy CURIE OR name
        ?species = <https://www.uniprot.org/taxonomy/9606> ||
        REGEX(LCASE(?speciesName), "human|homo sapiens")
    )
}
ORDER BY ?datasetName
```

**Note:** This query matches datasets by ontology CURIEs (MONDO for influenza, UniProt taxonomy for human) or by string matching on names.

## Cross-Resource Questions

### CQ11: Compare the number of datasets across different resources
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?resource (COUNT(DISTINCT ?dataset) AS ?datasetCount)
WHERE {
    ?dataset rdf:type schema:Dataset .
    BIND(REPLACE(STR(?dataset), "https://okn.wobd.org/dataset/([^/]+)/.*", "$1") AS ?resource)
}
GROUP BY ?resource
ORDER BY DESC(?datasetCount)
```

### CQ12: Find datasets that are accessible for free
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?resource ?url
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:url ?url ;
             schema:isAccessibleForFree true .
    BIND(REPLACE(STR(?dataset), "https://okn.wobd.org/dataset/([^/]+)/.*", "$1") AS ?resource)
}
ORDER BY ?resource ?datasetName
LIMIT 50
```

## Temporal Questions

### CQ13: What datasets were published or modified in 2024?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?dataset ?datasetName ?dateModified ?datePublished
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName .
    OPTIONAL { ?dataset schema:dateModified ?dateModified . }
    OPTIONAL { ?dataset schema:datePublished ?datePublished . }
    FILTER(
        (BOUND(?dateModified) && REGEX(STR(?dateModified), "^2024")) ||
        (BOUND(?datePublished) && REGEX(STR(?datePublished), "^2024"))
    )
}
ORDER BY DESC(?dateModified) DESC(?datePublished)
LIMIT 50
```

## Advanced Multi-Hop Questions

### CQ14: Find all datasets funded by NIAID that study COVID-19 and use human subjects
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?grantName
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName ;
             schema:healthCondition <http://purl.obolibrary.org/obo/MONDO_0100096> ;
             schema:species ?species ;
             schema:funding ?grant .
    ?species schema:name ?speciesName .
    ?grant schema:funder <https://ror.org/043z4tv69> ;
           schema:name ?grantName .
    FILTER(
        # Match human by UniProt taxonomy CURIE OR name
        ?species = <https://www.uniprot.org/taxonomy/9606> ||
        REGEX(LCASE(?speciesName), "human|homo sapiens")
    )
}
ORDER BY ?datasetName
```

### CQ15: What measurement techniques are used across datasets studying influenza?
**SPARQL Query:**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?technique (COUNT(DISTINCT ?dataset) AS ?datasetCount)
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:healthCondition ?disease ;
             schema:measurementTechnique ?tech .
    ?disease schema:name ?diseaseName .
    ?tech schema:name ?technique .
    FILTER(
        # Match influenza by MONDO CURIE OR name
        ?disease = <http://purl.obolibrary.org/obo/MONDO_0005812> ||
        CONTAINS(LCASE(?diseaseName), "influenza")
    )
}
GROUP BY ?technique
ORDER BY DESC(?datasetCount)
```

**Note:** This query matches datasets by either the MONDO ontology CURIE for influenza or by string matching on the disease name.

## Notes

- All queries use the OKN-WOBD namespace (`https://okn.wobd.org/`) for datasets
- External URIs are used for diseases (MONDO), species (UniProt), and organizations (ROR)
- Some queries may need adjustment based on the actual data loaded into your SPARQL endpoint

### Ontology CURIEs Used in Queries

Many queries use OR conditions to match by both ontology CURIEs and string names for better precision and coverage:

- **Influenza**: `MONDO:0005812`
- **Human**: UniProt taxonomy `9606` (Homo sapiens)
- **Mouse**: UniProt taxonomy `10090` (Mus musculus)
- **Stanford University**: ROR `00f54p054 `
- **COVID-19**: `MONDO:0100096`

**Note:** If the CURIEs in the queries don't match your data, you can:
1. Query your data to find the actual CURIEs used
2. Update the queries with the correct CURIEs
3. Or remove the CURIE condition and rely on string matching only

### Query Compatibility

**FRINK-Optimized Queries:**
- These queries are optimized for use with FRINK and use SPARQL 1.1 functions:
  - `CONTAINS()` for substring matching (CQ2, CQ8, CQ10, CQ15)
  - `LCASE()` for case-insensitive comparisons (CQ2, CQ3, CQ8, CQ10, CQ14, CQ15)
  - `REPLACE()` for extracting resource names from URIs (CQ4, CQ11, CQ12)
- All queries have been tested and validated using `scripts/test_competency_queries.py`

**Protege Compatibility:**
- These queries may not work in Protege due to limited SPARQL 1.1 function support:
  - Protege does not support `CONTAINS()` - use `REGEX()` with case-insensitive patterns instead
  - Protege does not support `LCASE()` - use `REGEX()` with `(?i)` flag instead
  - Protege may not support `REPLACE()` - use UNION with explicit resource matching or remove resource extraction
- If you need Protege-compatible versions, modify the queries accordingly or use the test script to validate alternative syntax

