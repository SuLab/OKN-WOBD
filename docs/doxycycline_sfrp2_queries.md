# Queries for Doxycycline → SFRP2 → Disease Network

This document contains SPARQL queries to retrieve the connections shown in the network graph visualization that displays Doxycycline → SFRP2 → Disease relationships.

## Overview

The network graph shows connections from three data sources:
- **Red lines**: GXA (Gene Expression Atlas) - gene expression data
- **Blue lines**: SPOKE-OKN - drug-gene relationships  
- **Green lines**: Ubergraph - gene-disease relationships

## Complete Federated Query

This query retrieves all connections across all three sources:

**Question:** "Find diseases connected to SFRP2 that is affected by Doxycycline."

**Query:** Available as a preset query in the web app, or use `DOXYCYCLINE_SFRP2_DISEASE_QUERY` from `web/wobd_web/preset_queries.py`

## Individual Connection Queries

### 1. Query SPOKE-OKN: Doxycycline → SFRP2 (Drug-Gene)

Find how Doxycycline affects SFRP2:

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT
    ?drug
    ?drugLabel
    ?gene
    ?geneSymbol
    ?predicate
    ?predicateLabel
WHERE {
    SERVICE <https://frink.apps.renci.org/spoke-okn/sparql> {
        ?drug ?predicate ?gene .
        
        # Filter for Doxycycline
        OPTIONAL {
            ?drug rdfs:label ?drugLabel .
            FILTER(LANG(?drugLabel) = "en")
        }
        FILTER(
            CONTAINS(LCASE(STR(?drugLabel)), "doxycycline") ||
            CONTAINS(LCASE(STR(?drug)), "doxycycline")
        )
        
        # Filter for SFRP2 gene
        ?gene biolink:symbol ?geneSymbol .
        FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
        
        # Get predicate label
        OPTIONAL {
            ?predicate rdfs:label ?predicateLabel .
            FILTER(LANG(?predicateLabel) = "en")
        }
    }
}
LIMIT 200
```

### 2. Query Ubergraph: SFRP2 → Diseases (Gene-Disease)

Find diseases associated with SFRP2:

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT
    ?gene
    ?geneSymbol
    ?disease
    ?diseaseLabel
    ?predicate
    ?predicateLabel
WHERE {
    SERVICE <https://frink.apps.renci.org/ubergraph/sparql> {
        # Find SFRP2 gene
        ?gene biolink:symbol ?geneSymbol .
        FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
        
        # Find diseases connected to SFRP2
        ?gene ?predicate ?disease .
        
        # Filter for disease entities
        ?disease a ?diseaseType .
        FILTER(STRSTARTS(STR(?diseaseType), "https://w3id.org/biolink/vocab/Disease") || 
               STRSTARTS(STR(?diseaseType), "http://purl.obolibrary.org/obo/MONDO"))
        
        # Get labels
        OPTIONAL {
            ?disease rdfs:label ?diseaseLabel .
            FILTER(LANG(?diseaseLabel) = "en")
        }
        OPTIONAL {
            ?predicate rdfs:label ?predicateLabel .
            FILTER(LANG(?predicateLabel) = "en")
        }
    }
}
LIMIT 200
```

### 3. Query GXA: SFRP2 Gene Expression (Up/Downregulated)

Find SFRP2 expression data (upregulated/downregulated in experiments):

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT
    ?gene
    ?geneSymbol
    ?experiment
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ?experimentLabel
    ?log2fc
    ?adjPValue
    ?expressionDirection
WHERE {
    SERVICE <https://frink.apps.renci.org/geneexpr/sparql> {
        # Find gene expression associations for SFRP2
        ?association a biolink:GeneExpressionMixin ;
            biolink:object ?gene ;
            biolink:subject ?experiment ;
            spokegenelab:log2fc ?log2fc ;
            spokegenelab:adj_p_value ?adjPValue .
        
        # Filter for SFRP2 gene
        ?gene biolink:symbol ?geneSymbol .
        FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
        
        # Determine if upregulated or downregulated
        BIND(IF(?log2fc > 0, "upregulated", "downregulated") AS ?expressionDirection)
        
        # Get experiment label
        OPTIONAL {
            ?experiment biolink:name ?experimentLabel .
        }
    }
}
ORDER BY DESC(?log2fc)
LIMIT 200
```

### 4. Combined Query: All SFRP2 Connections

Find all connections to/from SFRP2 across all sources:

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT
    ?source
    ?gene
    ?geneSymbol
    ?connectedEntity
    ?connectedEntityLabel
    ?connectionType
    ?predicate
    ?log2fc
WHERE {
    # Find SFRP2 gene (assume it exists in one of the sources)
    {
        SERVICE <https://frink.apps.renci.org/spoke-okn/sparql> {
            ?gene biolink:symbol ?geneSymbol .
            FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
            BIND("SPOKE-OKN" AS ?source)
            
            # Drug connections
            ?drug ?predicate ?gene .
            BIND(?drug AS ?connectedEntity)
            BIND("drug-gene" AS ?connectionType)
            OPTIONAL {
                ?drug rdfs:label ?connectedEntityLabel .
                FILTER(LANG(?connectedEntityLabel) = "en")
            }
        }
    }
    UNION
    {
        SERVICE <https://frink.apps.renci.org/ubergraph/sparql> {
            ?gene biolink:symbol ?geneSymbol .
            FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
            BIND("Ubergraph" AS ?source)
            
            # Disease connections
            ?gene ?predicate ?disease .
            BIND(?disease AS ?connectedEntity)
            BIND("gene-disease" AS ?connectionType)
            OPTIONAL {
                ?disease rdfs:label ?connectedEntityLabel .
                FILTER(LANG(?connectedEntityLabel) = "en")
            }
        }
    }
    UNION
    {
        SERVICE <https://frink.apps.renci.org/geneexpr/sparql> {
            ?association a biolink:GeneExpressionMixin ;
                biolink:object ?gene ;
                biolink:subject ?experiment ;
                spokegenelab:log2fc ?log2fc .
            
            ?gene biolink:symbol ?geneSymbol .
            FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
            BIND("GXA" AS ?source)
            BIND(?experiment AS ?connectedEntity)
            BIND("gene-expression" AS ?connectionType)
            BIND(spokegenelab:log2fc AS ?predicate)
            OPTIONAL {
                ?experiment biolink:name ?connectedEntityLabel .
            }
        }
    }
}
LIMIT 200
```

## Using These Queries

### In the Web App

1. The complete federated query is available as a preset query:
   - Question: "Find diseases connected to SFRP2 that is affected by Doxycycline."

2. To test individual queries, you can:
   - Use the web app with FRINK enabled
   - Copy/paste individual queries and test them directly against FRINK endpoints

### Testing Locally

For testing gene expression queries locally, use:
```bash
python scripts/test_preset_queries.py --file <file-containing-sfrp2>.ttl --verbose
```

## Notes

- **Predicates**: The actual predicates used may vary. Common ones include:
  - `biolink:decreases_expression_of`
  - `biolink:increases_expression_of`
  - `biolink:affects_expression_of`
  - `biolink:associated_with`
  - `biolink:related_to`

- **Gene Symbol Variations**: SFRP2 might be represented as:
  - `SFRP2`
  - `SFRP-2`
  - `sfrp2`

- **Disease Types**: Diseases may use:
  - Biolink Disease types
  - MONDO ontology terms
  - Other disease ontologies

## Adjusting Queries

If queries don't return expected results:

1. **Check predicates**: Query to see what predicates actually exist:
   ```sparql
   SELECT DISTINCT ?p WHERE {
       ?s ?p ?o .
       FILTER(CONTAINS(LCASE(STR(?p)), "express") || 
              CONTAINS(LCASE(STR(?p)), "disease") ||
              CONTAINS(LCASE(STR(?p)), "affect"))
   }
   ```

2. **Check gene symbol format**: Query to see how SFRP2 is represented:
   ```sparql
   SELECT ?gene ?symbol WHERE {
       ?gene biolink:symbol ?symbol .
       FILTER(CONTAINS(LCASE(STR(?symbol)), "sfrp"))
   }
   ```

3. **Check drug representation**: Query to see how Doxycycline is represented:
   ```sparql
   SELECT ?drug ?label WHERE {
       ?drug rdfs:label ?label .
       FILTER(CONTAINS(LCASE(STR(?label)), "doxycycline"))
   }
   ```

