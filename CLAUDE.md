# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OKN-WOBD extracts biomedical dataset metadata from the NIAID Data Ecosystem Discovery Portal and converts it to RDF for loading into ProtoOKN/FRINK knowledge graphs. The project has two main components:

1. **Core CLI** (`src/okn_wobd/`) - Fetch data from NIAID API and convert to RDF
2. **Demo Scripts** (`scripts/demos/`) - Cross-layer query demos integrating multiple biomedical data sources

## Common Commands

```bash
# Install package in development mode (requires Python >= 3.11)
pip install -e .

# Fetch dataset records from NIAID API
okn-wobd fetch --resource ImmPort
okn-wobd fetch --all                    # Fetch all default resources
okn-wobd fetch --resource ImmPort --restart  # Ignore checkpoints, start fresh

# Convert JSONL to RDF N-Triples
okn-wobd convert
okn-wobd convert --resource ImmPort

# Run demo scripts (from scripts/demos/)
cd scripts/demos && python demo_acta2_fibrosis.py

# Test competency SPARQL queries against local RDF
python scripts/test_competency_queries.py           # Test all queries
python scripts/test_competency_queries.py --query CQ2 --verbose

# Summarize downloaded data
python scripts/summarize_jsonl.py       # Output: reports/jsonl_summary.md
python scripts/list_jsonl_fields.py     # Output: reports/jsonl_fields.md
```

## Architecture

### Core Package (`src/okn_wobd/`)

- **`cli.py`**: Click CLI with `fetch` and `convert` commands. Handles pagination, automatic segmentation for large catalogs (>10k records), and checkpoint/resume logic.
- **`rdf_converter.py`**: Converts JSONL to RDF N-Triples using rdflib. Maps Schema.org vocabulary to external ontologies (MONDO for diseases, UniProt taxonomy for species, ROR for organizations).

### Demo Clients (`scripts/demos/`)

Four reusable API clients for cross-layer biomedical queries:

| Client | Data Layer | Input | Output |
|--------|-----------|-------|--------|
| `sparql_client.py` | Wikidata/FRINK | Gene symbol | Gene IDs, GO terms, UniProt |
| `cellxgene_client.py` | CellxGene Census | Gene + tissue + disease | Fold changes, cell type stats |
| `niaid_client.py` | NIAID Discovery | Keywords | Study metadata, GSE accessions |
| `archs4_client.py` | ARCHS4 (local HDF5) | GSE ID + genes | Bulk expression values |

**Dependency flow**: SPARQL, CellxGene, and NIAID queries are independent. ARCHS4 depends on GSE accessions from NIAID results.

### Data Flow

```
NIAID API → data/raw/*.jsonl → data/rdf/*.nt → FRINK/Protege
```

## Key Patterns

### NIAID API Segmentation
The Elasticsearch backend limits results to 10k. `cli.py` handles this via prefix-based segmentation on the `identifier` field, with checkpoint files (`*_state.json`) enabling resume after interruption.

### RDF Conversion
External URIs are preferred over internal URIs:
- Diseases: `http://purl.obolibrary.org/obo/MONDO_*`
- Species: `https://www.uniprot.org/taxonomy/*`
- DOIs: `https://doi.org/*`
- Both `owl:sameAs` and `schema:sameAs` are emitted for interoperability.

### Demo Scripts Environment
Copy `scripts/demos/.env.example` to `.env` and set `ARCHS4_DATA_DIR` to the directory containing ARCHS4 HDF5 files (~15GB each).

## Data Locations

- `data/raw/` - JSONL files from NIAID API (with `*_state.json` checkpoints)
- `data/rdf/` - N-Triples RDF output
- `docs/competency_questions.md` - SPARQL queries for validating the knowledge graph
- `queries/` - Operational SPARQL queries for FRINK

## Default Resources

The `--all` flag fetches these resources: ImmPort, VDJServer, Vivli, RADx Data Hub, Project Tycho.

## External Integrations

- **FRINK**: https://frink.apps.renci.org/ - Target knowledge graph
- **Wikidata**: https://query.wikidata.org/sparql - Gene/disease lookups via demo clients
- **CellxGene Census**: Single-cell RNA-seq expression data
- **ARCHS4**: Bulk RNA-seq from GEO (requires local HDF5 files)
