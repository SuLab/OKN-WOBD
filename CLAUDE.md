# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OKN-WOBD extracts biomedical dataset metadata from the NIAID Data Ecosystem Discovery Portal and converts it to RDF for loading into ProtoOKN/FRINK knowledge graphs. The project has three main components:

1. **Core CLI** (`src/okn_wobd/`) - Fetch data from NIAID API and convert to RDF
2. **ChatGEO** (`scripts/demos/chatgeo/`) - Natural language differential expression analysis using ARCHS4
3. **Reusable Packages** (`scripts/demos/`) - Modular packages for biomedical data integration:
   - `clients/` - Data source clients (SPARQL, NIAID, ARCHS4, CellxGene)
   - `frink/` - FRINK knowledge graph integration (registry, context, NL-to-SPARQL)
   - `analysis_tools/` - Reusable analysis tools (gene paths, neighborhoods, drug-disease, visualization)
4. **Questions** (`scripts/demos/questions/`) - Biological question investigations producing HTML reports

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

# Run biological question investigations (from scripts/demos/)
cd scripts/demos && python -m questions.run_all --list          # List all questions
cd scripts/demos && python -m questions.gene_disease_map        # Q1: Gene-disease map
cd scripts/demos && python -m questions.gene_neighborhood_map   # Q2: Gene neighborhood
cd scripts/demos && python -m questions.run_all                 # Run all questions

# Run analysis tools directly (from scripts/demos/)
cd scripts/demos && python -m analysis_tools.gene_paths SFRP2
cd scripts/demos && python -m analysis_tools.gene_neighborhood CD19 --html cd19.html
cd scripts/demos && python -m analysis_tools.go_disease_analysis --go-term GO:0030198 --disease "pulmonary fibrosis" --tissue lung

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

### Clients Package (`scripts/demos/clients/`)

Unified data source clients for cross-layer biomedical queries:

| Module | Data Layer | Key Classes | Description |
|--------|-----------|-------------|-------------|
| `sparql.py` | Wikidata/FRINK/Ubergraph/Fuseki | `SPARQLClient`, `QueryResult`, `GXAQueries` | Unified SPARQL client with named endpoints and `add_endpoint()` for custom servers |
| `cellxgene.py` | CellxGene Census | `CellxGeneClient`, `ExpressionStats` | Single-cell RNA-seq expression queries |
| `niaid.py` | NIAID Discovery | `NIAIDClient`, `SearchResult` | Dataset search with ontology annotations |
| `archs4.py` | ARCHS4 (local HDF5) | `ARCHS4Client`, `ARCHS4DataFile` | Bulk RNA-seq expression from GEO |
| `http_utils.py` | Shared | `create_session()` | HTTP session with retry logic |

Import from the package: `from clients import SPARQLClient, NIAIDClient, ARCHS4Client, CellxGeneClient`

**Dependency flow**: SPARQL, CellxGene, and NIAID queries are independent. ARCHS4 depends on GSE accessions from NIAID results. ChatGEO depends on `clients.archs4`.

### FRINK Package (`scripts/demos/frink/`)

FRINK knowledge graph integration tools:

- `registry.py` - Scrapes FRINK registry metadata (`FrinkRegistryClient`, `KnowledgeGraph`)
- `context.py` - Context file builder and API (`FrinkContext`, `build_context()`)
- `nl2sparql.py` - LLM-based NL→SPARQL translation (`FrinkNL2SPARQL`, `SPARQLGenerator`)

Import: `from frink import FrinkContext, FrinkNL2SPARQL, FrinkRegistryClient`

### Analysis Package (`scripts/demos/analysis_tools/`)

Reusable analysis tools:

- `gene_paths.py` - Gene-disease connections across SPOKE, Wikidata, Ubergraph (`GeneDiseasePathFinder`)
- `gene_neighborhood.py` - Gene neighborhood queries across FRINK graphs (`GeneNeighborhoodQuery`)
- `drug_disease.py` - Opposing drug/disease expression patterns via local GXA Fuseki (`find_drug_disease_genes`)
- `go_disease_analysis.py` - Multi-layer GO term disease analysis (KG + single-cell + bulk)
- `visualization.py` - vis.js network and Plotly visualizations (`PlotlyVisualizer`)

Import: `from analysis_tools import GeneDiseasePathFinder, GeneNeighborhoodQuery, PlotlyVisualizer`

### Questions (`scripts/demos/questions/`)

Biological question investigations. Each module answers a specific question using the reusable packages and produces an interactive HTML report:

- `gene_disease_map.py` - Q1: Gene-disease connections (SPOKE, Wikidata, Ubergraph)
- `gene_neighborhood_map.py` - Q2: Gene neighborhood across FRINK graphs
- `go_process_in_disease.py` - Q3: GO process genes in disease (multi-layer)
- `differential_expression.py` - Q4: DE analysis via ChatGEO (ARCHS4, g:Profiler)
- `drug_disease_targets.py` - Q5: Opposing drug/disease expression (GXA/Fuseki)
- `cross_layer_datasets.py` - Q6: Cross-layer KG → NIAID → ARCHS4 workflow
- `single_gene_deep_dive.py` - Q7: Single gene across all data sources
- `run_all.py` - Runner for all questions
- `_report.py` - Shared HTML report framework
- `reference_queries/` - Reference SPARQL queries

### Data Flow

```
NIAID API → data/raw/*.jsonl → data/rdf/*.nt → FRINK/Protege
                                                     ↓
                    Questions (Q1-Q7) query: FRINK + CellxGene + ARCHS4 + NIAID
                                                     ↓
                    ChatGEO: NL query → ARCHS4 → DE analysis → enrichment
                                                     ↓
                    Output: questions/output/*.html (interactive reports)
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
- `ANTHROPIC_API_KEY` - Required for LLM summaries in go_disease_analysis and ChatGEO interpretation

Demo scripts must be run from `scripts/demos/` so Python resolves package imports (clients, frink, analysis, chatgeo, questions, etc.).

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
