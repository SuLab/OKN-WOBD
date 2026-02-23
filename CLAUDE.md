# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OKN-WOBD extracts biomedical dataset metadata from the NIAID Data Ecosystem Discovery Portal and converts it to RDF for loading into ProtoOKN/FRINK knowledge graphs. The project has three main components:

1. **Core CLI** (`src/okn_wobd/`) - Fetch data from NIAID API and convert to RDF (N-Triples and Turtle)
2. **MCP Server** (`src/okn_wobd/mcp_server/`) - FastMCP server exposing analysis tools for AI assistants
3. **ChatGEO** (`scripts/demos/chatgeo/`) - Natural language differential expression analysis using ARCHS4
4. **Reusable Packages** (`scripts/demos/`) - Modular packages for biomedical data integration:
   - `clients/` - Data source clients (SPARQL, NIAID, ARCHS4, CellxGene)
   - `frink/` - FRINK knowledge graph integration (registry, context, NL-to-SPARQL)
   - `analysis_tools/` - Reusable analysis tools (gene paths, neighborhoods, drug-disease, visualization)
5. **Questions** (`scripts/demos/questions/`) - Biological question investigations producing HTML reports
6. **Web UI** (`web-v2/`) - Next.js chat interface for SPARQL querying against FRINK federation

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
cd scripts/demos && python -m chatgeo.cli "psoriasis in skin tissue" --mode study-matched --verbose
cd scripts/demos && python -m chatgeo.cli "psoriasis in skin tissue" --mode pooled --verbose

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

# GXA (Gene Expression Atlas) pipeline
okn-wobd gxa fetch --data-dir /path/to/gxa_data                    # Download from EBI FTP
okn-wobd gxa fetch --data-dir /path/to/gxa_data --experiment E-GEOD-5305  # Single experiment
okn-wobd gxa convert --data-dir /path/to/gxa_data --output-dir data/gxa_rdf
okn-wobd gxa run --data-dir /path/to/gxa_data --output-dir data/gxa_rdf   # Fetch + convert

# MCP server
okn-wobd-mcp                                          # Local stdio (for Claude Code)
OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp        # Remote HTTP
OKN_MCP_TRANSPORT=streamable-http OKN_MCP_PORT=9000 OKN_MCP_API_KEY=secret okn-wobd-mcp

# Run tests
pytest tests/ -v                                               # Unit tests
pytest tests/test_mcp_server.py -v                             # Single test file
RUN_INTEGRATION_TESTS=1 pytest tests/test_mcp_integration.py -v  # Integration tests (hits real endpoints)

# Summarize downloaded data
python scripts/summarize_jsonl.py       # Output: reports/jsonl_summary.md
python scripts/list_jsonl_fields.py     # Output: reports/jsonl_fields.md

# web-v2 (Next.js chat UI)
cd web-v2 && npm install && npm run dev   # Dev server on :3000
cd web-v2 && npm run build && npm start   # Production build
cd web-v2 && npm run lint                 # ESLint
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
| `sparql.py` | Wikidata/FRINK/Ubergraph | `SPARQLClient`, `QueryResult`, `GXAQueries` | Unified SPARQL client with named endpoints and `add_endpoint()` for custom servers |
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
- `drug_disease.py` - Opposing drug/disease expression patterns via GXA in FRINK (`find_drug_disease_genes`)
- `go_disease_analysis.py` - Multi-layer GO term disease analysis (KG + single-cell + bulk)
- `visualization.py` - vis.js network and Plotly visualizations (`PlotlyVisualizer`)

Import: `from analysis_tools import GeneDiseasePathFinder, GeneNeighborhoodQuery, PlotlyVisualizer`

### Questions (`scripts/demos/questions/`)

Biological question investigations. Each module answers a specific question using the reusable packages and produces an interactive HTML report:

- `gene_disease_map.py` - Q1: Gene-disease connections (SPOKE, Wikidata, Ubergraph)
- `gene_neighborhood_map.py` - Q2: Gene neighborhood across FRINK graphs
- `go_process_in_disease.py` - Q3: GO process genes in disease (multi-layer)
- `differential_expression.py` - Q4: DE analysis via ChatGEO (ARCHS4, g:Profiler)
- `drug_disease_targets.py` - Q5: Opposing drug/disease expression (GXA/FRINK)
- `cross_layer_datasets.py` - Q6: Cross-layer KG → NIAID → ARCHS4 workflow
- `single_gene_deep_dive.py` - Q7: Single gene across all data sources
- `run_all.py` - Runner for all questions
- `_report.py` - Shared HTML report framework
- `reference_queries/` - Reference SPARQL queries

### GXA Pipeline (`src/okn_wobd/gxa/`)

Downloads differential expression experiments from EBI Gene Expression Atlas FTP and converts to Biolink-compatible RDF Turtle. Each experiment produces one `.ttl` file with study metadata, assay contrasts, DE genes (with log2fc/p-value), and pathway enrichment.

Key modules: `downloader.py` (FTP), `parser.py` (IDF/SDRF/config/analytics), `pipeline.py` (orchestration), `rdf_builder.py` (Biolink RDF output).

### MCP Server (`src/okn_wobd/mcp_server/`)

FastMCP server wrapping `analysis_tools` and `chatgeo` packages. Supports stdio (local), streamable-http, and SSE transports. Config templates in `config/mcp-dev.json` and `config/mcp-remote.json`.

- `server.py` - Server setup, transport selection, logging. Redirects stdout→stderr (MCP uses stdout for JSON-RPC).
- `tools_analysis.py` - SPARQL-based tools: `gene_disease_paths`, `gene_neighborhood`, `drug_disease_opposing_expression`
- `tools_chatgeo.py` - ChatGEO tools with background job dispatch: `differential_expression`, `find_samples`, `get_sample_metadata`, `get_analysis_result`, `enrichment_analysis`, `resolve_disease_ontology`

### Web UI (`web-v2/`)

Next.js 14 App Router with TypeScript/React/Tailwind. Three-lane SPARQL query system:
- **Lane A** (default): LLM outputs intent JSON → app generates SPARQL from vetted templates
- **Lane B** (fallback): LLM generates SPARQL directly, constrained by context pack schema hints
- **Lane C** (expert): User writes SPARQL manually

Key directories: `app/api/tools/` (Tool Service API), `lib/context-packs/` (context loader), `lib/sparql/` (validation/execution), `context/packs/wobd.yaml` (default config), `context/graphs/` (graph metadata JSON).

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

### MCP Background Jobs
Long-running tools (`differential_expression`, `find_samples`, `get_sample_metadata`) dispatch to background threads and return a `job_id` immediately. Clients poll with `get_analysis_result()` every 30-60s. This avoids the ~60s MCP tool timeout for analyses that can take 5+ minutes.

### ARCHS4 SQLite Index
`clients/archs4_index.py` builds a one-time SQLite index of ~1.05M ARCHS4 samples (~15s build, ~1.4GB). Stored as `.metadata.db` alongside HDF5 files. Provides ~60,000x speedup for metadata queries vs direct HDF5 access. Transparent fallback to HDF5 on index errors.

### ChatGEO Analysis Modes
- **auto** (default): Tries study-matched meta-analysis first, falls back to study-prioritized pooling, then basic pooling
- **study-matched**: Independent DE per GEO study, combined via Stouffer/Fisher meta-analysis. Eliminates batch effects.
- **pooled**: All samples in one comparison. Fast but susceptible to batch effects.

### Demo Scripts Environment
Copy `scripts/demos/.env.example` to `.env` and configure:
- `ARCHS4_DATA_DIR` - Directory containing ARCHS4 HDF5 files (~58GB each, required for ARCHS4/ChatGEO)
- `ANTHROPIC_API_KEY` - Required for LLM summaries in go_disease_analysis and ChatGEO interpretation

MCP server environment variables: `OKN_MCP_TRANSPORT` (stdio|streamable-http|sse), `OKN_MCP_HOST`, `OKN_MCP_PORT`, `OKN_MCP_API_KEY`, `OKN_MCP_LOG_LEVEL`.

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
- `data/gxa_rdf/` - GXA Turtle RDF output
- `docs/competency_questions.md` - SPARQL queries for validating the knowledge graph
- `queries/` - Operational SPARQL queries for FRINK

## Default Resources

The `--all` flag fetches these resources: ImmPort, VDJServer, Vivli, RADx Data Hub, Project Tycho.

## External Integrations

- **FRINK**: https://frink.apps.renci.org/ - Target knowledge graph (Wikidata, Ubergraph, SPOKE)
- **Wikidata**: https://query.wikidata.org/sparql - Gene/disease lookups via demo clients
- **CellxGene Census**: Single-cell RNA-seq expression data
- **ARCHS4**: Bulk RNA-seq from GEO (requires local HDF5 files)
- **GXA**: Gene Expression Atlas via FRINK (`https://frink.apps.renci.org/gene-expression-atlas-okn/sparql`)
- **g:Profiler**: Gene set enrichment analysis (GO, KEGG, Reactome)
