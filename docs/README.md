# OKN-WOBD Knowledge Graph Documentation

## Overview

The OKN-WOBD knowledge graph contains RDF representations of datasets from the NIAID Data Ecosystem (NDE), including data from:

- **ImmPort**: Immunology Database and Analysis Portal
- **VDJServer**: V(D)J Recombination Database
- **Vivli**: Global Clinical Trials Data Sharing Platform
- **RADx Data Hub**: Rapid Acceleration of Diagnostics Data Hub
- **Project Tycho**: Disease Surveillance Data

## Namespace

All OKN-WOBD entities use the namespace: `https://okn.wobd.org/`

Dataset URIs follow the pattern: `https://okn.wobd.org/dataset/{resource}/{id}`

## Data Sources

The source data is fetched from the NIAID Data Ecosystem Discovery Portal API:
- API Base URL: `https://api.data.niaid.nih.gov/v1/query`
- Data is extracted as JSON-LD with Schema.org vocabulary
- Converted to RDF N-Triples format for loading into FRINK

## Vocabulary Usage

### Primary Vocabulary: Schema.org

The knowledge graph primarily uses [Schema.org](https://schema.org/) vocabulary:

- **Classes**: `schema:Dataset`, `schema:Person`, `schema:Organization`, `schema:MonetaryGrant`, `schema:DefinedTerm`, `schema:DataCatalog`, `schema:DataDownload`
- **Properties**: `schema:name`, `schema:description`, `schema:author`, `schema:funding`, `schema:healthCondition`, `schema:species`, `schema:infectiousAgent`, etc.

### External Vocabulary Reuse

Following Proto-OKN best practices, we reuse identifiers from well-known ontologies:

- **Diseases**: [MONDO](http://purl.obolibrary.org/obo/MONDO_*) ontology URIs
- **Species**: [UniProt Taxonomy](https://www.uniprot.org/taxonomy/*) URIs
- **Infectious Agents**: UniProt Taxonomy URIs
- **Organizations**: [ROR](https://ror.org/*) identifiers when available
- **DOIs**: Converted to `https://doi.org/*` URIs

### Interoperability Mappings

- `owl:sameAs` mappings are used for external identifiers (DOIs, external URIs)
- `schema:sameAs` is also included for Schema.org compatibility
- RDFS axioms are included for classes and properties

## RDFS Axioms

The knowledge graph includes RDFS axioms per Proto-OKN best practices:

- **Class Declarations**: All Schema.org classes used are declared as `rdfs:Class`
- **Property Domains**: Properties have domain assertions (e.g., `schema:author rdfs:domain schema:Dataset`)
- **Property Ranges**: Properties have range assertions (e.g., `schema:author rdfs:range schema:Person`)

## SPARQL Queries

This repository contains two types of SPARQL queries:

### Competency Questions

See [competency_questions.md](./competency_questions.md) for 15+ natural language questions with corresponding SPARQL queries. These are **high-level domain questions** that test and validate the knowledge graph design.

Example questions:
- How many datasets are available from ImmPort?
- What datasets are available for influenza research?
- Which datasets are funded by NIAID?
- What infectious agents are studied across all datasets?

These queries are optimized for FRINK and use SPARQL 1.1 functions (`CONTAINS`, `LCASE`, `REPLACE`). They can be tested locally using `scripts/test_competency_queries.py`.

### Operational Queries

The [`queries/`](../queries/) directory contains **utility queries** for working with specific datasets and exploring the data:

- **`immport_by_id.sparql`**: Queries for finding and exploring specific ImmPort datasets by ID (e.g., "Find dataset SDY2580", "Get all properties for a dataset")
- **`frink_immport.sparql`**: Simple exploration queries for FRINK (e.g., "Find datasets with names", "Count ImmPort datasets")

These are practical, operational queries for day-to-day data exploration, while competency questions validate the overall knowledge graph design.

## RDF Validation

### Syntax Validation

Validate RDF syntax using [Apache Jena RIOT](https://jena.apache.org/documentation/io/):

```bash
riot --validate data/rdf/immport.nt
```

Or using Python with rdflib:

```python
from rdflib import Graph
g = Graph()
g.parse("data/rdf/immport.nt", format="nt")
# If no errors, syntax is valid
```

### SHACL Validation (Advanced)

For constraint validation, use [PySHACL](https://pypi.org/project/pyshacl/):

```bash
pip install pyshacl
pyshacl -s data/rdf/immport.nt
```

## Querying the Knowledge Graph

### In Protege

1. Open Protege
2. Load your `.nt` file
3. Use the SPARQL Query tab to run queries
4. See `queries/` directory for example queries

### In FRINK

The knowledge graph is designed for loading into [FRINK](https://frink.renci.org/):

1. Use FRINK's query interface at https://frink.apps.renci.org/
2. Select appropriate data sources
3. Run federated queries across multiple graphs
4. See `queries/frink_immport.sparql` for FRINK-compatible queries

### Example SPARQL Query

```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?dataset ?name ?doi
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?name .
    OPTIONAL { ?dataset schema:sameAs ?doi . }
    FILTER(REGEX(STR(?dataset), "^https://okn\\.wobd\\.org/dataset/immport/"))
}
LIMIT 10
```

## Data Conversion Process

1. **Fetch**: Use `okn-wobd fetch` to download JSONL from NDE API
2. **Convert**: Use `okn-wobd convert` to generate RDF N-Triples
3. **Validate**: Check RDF syntax (see RDF Validation section)
4. **Load**: Import into FRINK or other triple store

## Schema Diagram

A visual representation of the knowledge graph schema would show:

```
┌─────────────┐
│   Dataset   │
└──────┬──────┘
       │
       ├─── schema:author ─────>  ┌────────┐
       │                          │ Person │
       ├─── schema:funding ────>  └────────┘
       │       │                    ┌──────────────────┐
       │       └──> schema:funder ─>│  Organization    │
       │                            └──────────────────┘
       ├─── schema:healthCondition ─>  ┌─────────────┐
       │                               │ DefinedTerm │
       ├─── schema:species ─────────>  │ (MONDO URI) │
       │                               └─────────────┘
       ├─── schema:infectiousAgent ─>  ┌─────────────┐
       │                               │ DefinedTerm │
       └─── schema:includedInDataCatalog ─> ┌──────────────┐
                                            │ DataCatalog  │
                                            └──────────────┘
```

## Best Practices Compliance

This knowledge graph follows [Proto-OKN Best Practice Guidelines](https://kastle-lab.github.io/education-gateway/resource-pages/graph-construction-guidelines.html):

- ✅ Own namespace (`https://okn.wobd.org/`)
- ✅ Reuses IRIs from well-known vocabularies (MONDO, UniProt, ROR)
- ✅ Includes RDFS axioms for classes and properties
- ✅ Uses `owl:sameAs` for external identifier mappings
- ✅ Provides competency questions and SPARQL queries
- ✅ Documentation of data sources and conversion process

## Contact

For questions or issues, please contact the OKN-WOBD team.

## License

[Add license information as appropriate for your project]


