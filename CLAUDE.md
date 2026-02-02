# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OKN-WOBD extracts biomedical dataset metadata from the NIAID Data Ecosystem Discovery Portal and converts it to RDF for loading into ProtoOKN/FRINK knowledge graphs. The project has three main components:

1. **Core CLI** (`src/okn_wobd/`) - Fetch data from NIAID API and convert to RDF
2. **ChatGEO** (`scripts/demos/chatgeo/`) - Natural language differential expression analysis using ARCHS4
3. **Demo Scripts** (`scripts/demos/`) - Cross-layer query demos integrating multiple biomedical data sources

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

# Run ChatGEO differential expression analysis (from scripts/demos/)
cd scripts/demos && python -m chatgeo.cli "psoriasis in skin tissue" --verbose

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

### ChatGEO (`scripts/demos/chatgeo/`)

Natural language interface for differential expression analysis. Takes a plain-text disease query, finds matching samples in ARCHS4, and runs DE analysis with enrichment.

Pipeline: **query parsing → synonym expansion → ARCHS4 sample discovery → expression retrieval → preprocessing → DESeq2 testing → g:Profiler enrichment → report generation**

Key modules:
- `cli.py` - Entry point, parses natural language into disease + tissue terms
- `sample_finder.py` - Finds disease and control samples in ARCHS4 metadata (pooled or study-matched modes)
- `de_analysis.py` - Statistical testing: DESeq2 (default), Mann-Whitney U, Welch t-test
- `query_builder.py` - Expands tissue/disease terms with synonyms for broader matching
- `enrichment_analyzer.py` - GO, KEGG, Reactome enrichment via g:Profiler
- `interpretation.py` - LLM-based interpretation of DE results

Additional dependencies beyond core: `numpy`, `pandas`, `scipy`, `pydeseq2`, `gprofiler-official`

### Demo Clients (`scripts/demos/`)

Reusable API clients for cross-layer biomedical queries:

| Client | Data Layer | Input | Output |
|--------|-----------|-------|--------|
| `sparql_client.py` | Wikidata/FRINK/Ubergraph | Gene symbol, SPARQL | Gene IDs, GO terms, disease associations |
| `cellxgene_client.py` | CellxGene Census | Gene + tissue + disease | Fold changes, cell type stats |
| `niaid_client.py` | NIAID Discovery | Keywords | Study metadata, GSE accessions |
| `archs4_client.py` | ARCHS4 (local HDF5) | GSE ID + genes | Bulk expression values |
| `fuseki_client.py` | Local Fuseki/GXA | SPARQL | Gene expression atlas results |
| `frink_context_builder.py` | FRINK | Endpoint URL | Schema context files for LLM query generation |

**Dependency flow**: SPARQL, CellxGene, and NIAID queries are independent. ARCHS4 depends on GSE accessions from NIAID results. ChatGEO depends on ARCHS4 client.

### Analysis Scripts (`scripts/demos/`)

- `gene_disease_paths.py` - Finds gene-disease connections across SPOKE, Wikidata, and Ubergraph
- `go_disease_analyzer.py` - Multi-layer analysis: KG → single-cell (CellxGene) → bulk validation (ARCHS4)
- `query_drug_down_disease_up.py` - Finds opposing drug/disease expression patterns in local GXA Fuseki
- `frink_nl2sparql.py` - Natural language to SPARQL translation using LLMs + FRINK context

### Data Flow

```
NIAID API → data/raw/*.jsonl → data/rdf/*.nt → FRINK/Protege
                                                     ↓
                            Demo scripts query: FRINK + CellxGene + ARCHS4
                                                     ↓
                            ChatGEO: NL query → ARCHS4 → DE analysis → enrichment
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
Copy `scripts/demos/.env.example` to `.env` and configure:
- `ARCHS4_DATA_DIR` - Directory containing ARCHS4 HDF5 files (~15GB each, required for ARCHS4/ChatGEO)
- `ANTHROPIC_API_KEY` - Required for LLM summaries in go_disease_analyzer and ChatGEO interpretation

Demo scripts must be run from `scripts/demos/` so Python resolves local imports (chatgeo, archs4_client, etc.).

### Demo Dependencies
Demo scripts require packages beyond the core `okn-wobd` install:
```bash
pip install pandas scipy numpy pydeseq2 gprofiler-official  # ChatGEO / DE analysis
pip install SPARQLWrapper requests                           # SPARQL / NIAID clients
pip install cellxgene-census                                # CellxGene client
pip install h5py                                            # ARCHS4 HDF5 access
pip install plotly                                          # Visualizations
pip install anthropic                                       # LLM summaries
```

## Data Locations

- `data/raw/` - JSONL files from NIAID API (with `*_state.json` checkpoints)
- `data/rdf/` - N-Triples RDF output
- `docs/competency_questions.md` - SPARQL queries for validating the knowledge graph
- `queries/` - Operational SPARQL queries for FRINK

## Default Resources

The `--all` flag fetches these resources: ImmPort, VDJServer, Vivli, RADx Data Hub, Project Tycho.

## External Integrations

- **FRINK**: https://frink.apps.renci.org/ - Target knowledge graph (Wikidata, Ubergraph, SPOKE)
- **Wikidata**: https://query.wikidata.org/sparql - Gene/disease lookups via demo clients
- **CellxGene Census**: Single-cell RNA-seq expression data
- **ARCHS4**: Bulk RNA-seq from GEO (requires local HDF5 files)
- **GXA/Fuseki**: Gene Expression Atlas via local Fuseki server (`http://localhost:3030/GXA-v2/sparql`)
- **g:Profiler**: Gene set enrichment analysis (GO, KEGG, Reactome)
