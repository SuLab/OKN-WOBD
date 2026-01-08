# NDE ↔ SPOKE-GeneLab Connection Queries

This folder contains SPARQL queries for exploring connections between the NIAID Data Ecosystem (NDE) and NASA's GeneLab (spoke-genelab) knowledge graphs in FRINK.

## Endpoints

| Graph | SPARQL Endpoint |
|-------|-----------------|
| NDE | https://frink.apps.renci.org/nde/sparql |
| spoke-genelab | https://frink.apps.renci.org/spoke-genelab/sparql |
| Federated | https://frink.apps.renci.org/sparql |

## Current Connection Status

### Working Connection: Shared Species (Taxonomy)

Both graphs contain studies/datasets about **Mus musculus** (mouse, taxon ID 10090), but use different URI schemes:

- **spoke-genelab**: `http://purl.obolibrary.org/obo/NCBITaxon_10090`
- **NDE**: `https://www.uniprot.org/taxonomy/10090`

These could be linked via `owl:sameAs` equivalence.

### Conceptual Connection Path (Not Yet in KG)

The following path exists in the real world but is not fully represented in the current KGs:

```
GeneLab Study (OSD-690)
    ↓ (publication link - NOT IN KG)
PubMed Article (PMID:37626149)
    ↓ (GEO reference - NOT IN KG)
GEO Dataset (GSE240654)
    ↓ (indexed by NIAID)
NDE Resource (data.niaid.nih.gov/resources?id=gse240654)
```

**Missing data:**
1. GeneLab studies don't have publication links (PMID) in the KG
2. NDE doesn't have GEO datasets indexed in the current FRINK KG
3. No publication-to-dataset linkage exists

## Query Files

| File | Description |
|------|-------------|
| `genelab_studies.sparql` | List GeneLab studies with metadata |
| `nde_datasets.sparql` | List NDE datasets with metadata |
| `species_connection.sparql` | Find resources sharing mouse (taxon 10090) |
| `genelab_study_details.sparql` | Get full details for a specific GeneLab study |

## Example: Species-Based Connection

This query would work if run against a federated endpoint with `owl:sameAs` linking the taxonomy URIs:

```sparql
PREFIX schema: <http://schema.org/>
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX genelab: <https://purl.org/okn/frink/kg/spoke-genelab/schema/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?nde_dataset ?nde_name ?genelab_study ?genelab_title
WHERE {
  # NDE mouse datasets
  SERVICE <https://frink.apps.renci.org/nde/sparql> {
    ?nde_dataset a schema:Dataset .
    ?nde_dataset schema:species <https://www.uniprot.org/taxonomy/10090> .
    ?nde_dataset schema:name ?nde_name .
  }

  # GeneLab mouse studies
  SERVICE <https://frink.apps.renci.org/spoke-genelab/sparql> {
    ?genelab_study a biolink:Study .
    ?genelab_study genelab:taxonomy <http://purl.obolibrary.org/obo/NCBITaxon_10090> .
    ?genelab_study genelab:project_title ?genelab_title .
  }
}
LIMIT 100
```

## Key URIs

### GeneLab Study Example
- **URI**: `https://purl.org/okn/frink/kg/spoke-genelab/node/OSD-100`
- **Type**: `https://w3id.org/biolink/vocab/Study`
- **Title**: Rodent Research 1
- **Organism**: Mus musculus

### GeneLab Schema Namespace
- Properties: `https://purl.org/okn/frink/kg/spoke-genelab/schema/`
- Nodes: `https://purl.org/okn/frink/kg/spoke-genelab/node/`

### NDE Schema
- Uses Schema.org vocabulary (`http://schema.org/`)
- Dataset type: `schema:Dataset`
