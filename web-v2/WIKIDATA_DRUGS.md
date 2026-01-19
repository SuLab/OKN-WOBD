# Wikidata Drug Support

This document describes the Wikidata drug grounding feature added to support drug/medication entity queries.

## Overview

The system now supports grounding drug and medication names to Wikidata identifiers, which can be used to query datasets that use Wikidata as their drug vocabulary.

## Architecture

### 1. Wikidata Client (`lib/ontology/wikidata-client.ts`)

A new client that searches the Wikidata SPARQL endpoint for drugs/medications:

- **`searchWikidataDrugs(searchTerm)`**: Searches for drugs using multiple strategies (all case-insensitive)
  - Exact match on primary label (score 4) - matches the main `rdfs:label` exactly
  - Exact match on alias/synonym (score 3) - matches `skos:altLabel` or other synonyms exactly
  - Partial match (score 2) - substring match on label or alias
  - Weak match (score 1) - loose match

- **`groundDrugToWikidata(drugName)`**: Main grounding function that filters results to likely drugs

- Uses Wikidata's medication class (`wdt:P31/wdt:P279* wd:Q12140`)

### 2. Ontology Mapping Update

Updated `lib/ontology/ontology-mapping.ts`:

```typescript
drug: {
  domain: "drug",
  ontology: "CHEBI,Wikidata",
  description: "Drugs, medications, and chemical compounds (searches both CHEBI and Wikidata)",
}
```

### 3. Preprocessor Integration

Updated `lib/ontology/preprocessor.ts` to handle Wikidata grounding:

- Detects drug/medication entities from the ontology mapping
- Calls `groundDrugToWikidata()` to get Wikidata identifiers
- Converts Wikidata results to the standard grounding format
- Supports dual CHEBI/Wikidata lookup (currently Wikidata only)

### 4. SPARQL Templates

Added `buildWikidataDrugQuery()` in `lib/ontology/templates.ts`:

- Queries the Wikidata graph for datasets related to specific drug IRIs
- Supports optional text matching on drug names for high-confidence matches
- Uses the `wikidata` graph from the FRINK federation

### 5. Dataset Search Template

Updated `lib/templates/templates/dataset_search.ts`:

- Added handling for drug/medication entities
- Populates the `drugs` slot with Wikidata IRIs
- Calls `buildWikidataDrugQuery()` to generate the SPARQL query

### 6. Intent Route

Updated `app/api/tools/nl/intent/route.ts`:

- Detects drug/medication entity types
- Populates `intent.slots.drugs` with Wikidata IRIs
- Logs drug terms being used for the query

## Usage Example

**Query**: "Find datasets related to aspirin"

1. **Entity Identification**: LLM identifies "aspirin" as a drug entity
2. **Wikidata Grounding**: System searches Wikidata and finds "Q421094" (aspirin)
3. **SPARQL Generation**: Creates query using Wikidata IRI `http://www.wikidata.org/entity/Q421094`
4. **Execution**: Queries the `wikidata` graph in FRINK federation

## Wikidata Integration

The system uses the Wikidata SPARQL endpoint:
- **Endpoint**: `https://query.wikidata.org/sparql`
- **Class**: `wd:Q12140` (medication)
- **Properties**: Uses `wdt:P31/wdt:P279*` for transitive instance-of/subclass-of relationships

## Graph Requirements

The SPARQL queries assume:
- A `wikidata` graph is available in the FRINK federation
- Datasets are linked to Wikidata drug entities (typically via `schema:about` or similar)

## Future Enhancements

- **CHEBI Integration**: Add CHEBI grounding via OLS alongside Wikidata
- **Schema Validation**: Confirm actual predicates used to link datasets to drugs
- **Result Merging**: Merge CHEBI and Wikidata results when both are available
- **Caching**: Add caching for Wikidata lookups to reduce API calls

## Testing

Example queries to test:
- "Find datasets related to aspirin"
- "Show studies about COVID-19 vaccines"
- "Datasets using Tocilizumab"
- "Research on influenza medications"

## Files Changed

1. `web-v2/lib/ontology/wikidata-client.ts` (new)
2. `web-v2/lib/ontology/ontology-mapping.ts`
3. `web-v2/lib/ontology/preprocessor.ts`
4. `web-v2/lib/ontology/templates.ts`
5. `web-v2/lib/templates/templates/dataset_search.ts`
6. `web-v2/app/api/tools/nl/intent/route.ts`
7. `web-v2/lib/ontology/index.ts`
