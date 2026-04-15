# OKN-WOBD

Extract data from the [NIAID Data Ecosystem Discovery Portal](https://data.niaid.nih.gov/) and convert for loading into [ProtoOKN](https://www.proto-okn.net/).

## Environment Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Key variables:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | LLM features (ChatGEO interpretation, NL-to-SPARQL, GO disease summaries) |
| `ARCHS4_DATA_DIR` | Path to ARCHS4 HDF5 files (~58 GB each, required for ChatGEO / DE analysis) |
| `OKN_MCP_TRANSPORT` | MCP server transport: `stdio` (default), `streamable-http`, or `sse` |

See `.env.example` for the full list of options. The `.env` file is gitignored.

## Python Environment Setup

Use `pyenv` to install the Python version needed, then create an isolated `venv` in the repository:

```bash
pyenv install 3.12.6
pyenv local 3.12.6
python -m venv .venv
source .venv/bin/activate     # on Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

## Fetching NDE Data

Run the Click CLI (installed as the `okn-wobd` console script) to download dataset records for one or more resources. By default, results are written to `data/raw` as JSON Lines (`*.jsonl`) with matching checkpoint files (`*_state.json`) to support restarts.

```bash
okn-wobd fetch --resource ImmPort
# or, equivalently:
python -m okn_wobd.cli fetch --resource ImmPort
```

### Options

- `--all`: Fetch all available resources from the NDE API (automatically discovers all Dataset Repositories). Resources listed in `src/okn_wobd/excluded_resources.py` are excluded.
- `--resource`: Repeatable; defaults to `ImmPort` when omitted. Examples: `ImmPort`, `"VDJ Server"`, `Vivli`, `RADx`, `PDB`, `"Project TYCHO"`.
- `--output-dir`: Directory for saved data and checkpoints (default: `data/raw`).
- `--page-size`: Batch size for API pagination (default: 100, maximum: 1000).
- `--facet-size`: Passed through to the API facet parameter (default: 10).
- `--restart`: Ignore previous checkpoints and start from the first page.
- `--verbose`: Emit detailed logging.
- `--max-window`: Maximum result window before automatic segmentation (default: 10,000).
- `--segment-field`, `--segment-charset`, `--segment-max-length`: Controls for prefix-based segmentation when a catalog exceeds the result window.

### Restarting After Failures

The CLI records progress for each resource in `<output-dir>/<resource>_state.json`. Rerun the command without `--restart` to resume where it left off. Supply `--restart` to discard prior results and fetch everything again from the beginning.

### Example: Fetch All Available Dataset Repository Resources

```bash
okn-wobd fetch --all
```

This queries the NDE API to discover all available dataset repository resources and fetches data for each one (excluding resources configured in `src/okn_wobd/excluded_resources.py`, such as "Protein Data Bank").

### Example: Fetch Multiple Specific Resources

```bash
python -m okn_wobd.cli fetch \
  --resource ImmPort \
  --resource "VDJ Server" \
  --resource Vivli
```

This will create separate JSONL and checkpoint files for each resource under `data/raw/`.

### Handling Resources with >10k Records

Elasticsearch-backed endpoints limit `from + size <= 10,000`. When a catalog (for example, `Protein Data Bank`) exceeds that window, the CLI automatically partitions requests by prefix on the `identifier` field. You can tune the behavior:

```bash
okn-wobd fetch \
  --resource "Protein Data Bank" \
  --max-window 10000 \
  --segment-field identifier \
  --segment-charset 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ \
  --segment-max-length 8
```

The state file tracks both the current segment and offset so interrupted runs can resume without re-downloading data.

## Summarizing Downloaded JSONL Files

After fetching data, generate a quick overview of record counts and coverage of disease/species/infectious-agent metadata:

```bash
python scripts/summarize_jsonl.py
```

The script scans `data/raw/*.jsonl`, writes the results to `reports/jsonl_summary.md`, and prints the table to stdout.

## Listing Top-Level Fields in JSONL Files

```bash
python scripts/list_jsonl_fields.py
```

This writes a field inventory to `reports/jsonl_fields.md`.

## Converting JSONL to RDF N-Triples

Convert dataset records from JSONL format to RDF N-Triples (`.nt`) format for loading into FRINK:

```bash
okn-wobd convert
```

### Options

- `--input-dir`: Directory containing JSONL files (default: `data/raw`).
- `--output-dir`: Directory to write N-Triples files (default: `data/rdf`).
- `--resource`: Repeatable; convert specific resources. If omitted, converts all JSONL files found in input directory.
- `--log-file`: Path to write conversion log file (includes warnings about bad URIs, skipped duplicates, etc.). If omitted, logs only appear in terminal.

### Examples

```bash
# Convert all resources
okn-wobd convert

# Convert specific resources
okn-wobd convert --resource ImmPort --resource "VDJ Server"

# Specify custom input/output directories
okn-wobd convert --input-dir data/raw --output-dir data/rdf

# Save conversion logs to a file (useful for reporting data quality issues)
okn-wobd convert --log-file reports/conversion_log.txt

# Convert with logging for a specific resource
okn-wobd convert --resource ImmPort --log-file reports/immport_conversion_log.txt
```

The converter generates one `.nt` file per resource in the output directory. Each dataset is assigned a URI in the `https://okn.wobd.org/` namespace using the pattern `https://okn.wobd.org/dataset/{resource}/{_id}`.

The converter uses external URIs for shared entities:
- **Diseases**: MONDO ontology URIs (e.g., `http://purl.obolibrary.org/obo/MONDO_*`)
- **Species**: UniProt taxonomy URIs (e.g., `https://www.uniprot.org/taxonomy/*`)
- **Infectious Agents**: UniProt taxonomy URIs
- **Organizations**: ROR identifiers when available (e.g., `https://ror.org/*`)
- **DOIs**: Converted to `https://doi.org/*` URIs

The converter follows [Proto-OKN Best Practice Guidelines](https://kastle-lab.github.io/education-gateway/resource-pages/graph-construction-guidelines.html):
- ✅ Includes RDFS axioms for Schema.org classes (`rdfs:Class` declarations)
- ✅ Includes RDFS domain and range assertions for properties
- ✅ Adds `owl:sameAs` mappings alongside `schema:sameAs` for external identifiers

Elasticsearch metadata fields (`_score`, `_ignored`, `@version`) are excluded from the RDF output.

## Testing Competency Queries

After converting data to RDF, you can test the competency question SPARQL queries against your local data:

```bash
# Test all queries
python scripts/test_competency_queries.py

# Test a specific query
python scripts/test_competency_queries.py --query CQ2

# Show detailed results including sample data
python scripts/test_competency_queries.py --query CQ2 --verbose
```

### Options

- `--rdf-dir`: Directory containing RDF `.nt` files (default: `data/rdf`).
- `--queries-file`: Markdown file with competency questions (default: `docs/competency_questions.md`).
- `--query`: Test only a specific query (e.g., `CQ2` or `CQ10`).
- `--verbose`: Show query results and detailed error messages.

The script extracts SPARQL queries from the markdown file, loads all RDF files from the specified directory, and executes each query to verify it works correctly. This is useful for:
- Validating queries before using them in Protege or FRINK
- Testing query syntax and compatibility
- Verifying queries return expected results against your data

See the [documentation](./docs/README.md) for more details, including competency questions and SPARQL query examples.

## GXA (Gene Expression Atlas) to RDF

The `gxa` command group converts differential expression experiment data from the [EBI Gene Expression Atlas](https://www.ebi.ac.uk/gxa/) into Biolink-compatible RDF (Turtle format). See **[src/okn_wobd/gxa/README.md](src/okn_wobd/gxa/README.md)** for full documentation including URI patterns, gene ID resolution, filtering thresholds, and example SPARQL queries.

Quick start:

```bash
# Download and convert all GXA experiments
okn-wobd gxa run --data-dir /path/to/gxa_data --output-dir data/gxa_rdf

# Single experiment
okn-wobd gxa run --data-dir /path/to/gxa_data --output-dir data/gxa_rdf \
    --experiment E-GEOD-5305
```
## ChatGEO: Differential Expression Analysis

ChatGEO provides natural language differential expression analysis using ARCHS4 bulk RNA-seq data. It searches ARCHS4 metadata for disease/control samples, runs statistical testing, and performs gene set enrichment via g:Profiler.

### Analysis Modes

ChatGEO supports three analysis modes to control batch effects:

- **`auto` (default)**: Tiered fallback strategy:
  1. Tries study-matched meta-analysis first (per-study DE + Stouffer/Fisher combination)
  2. Falls back to study-prioritized pooling (controls from test studies first)
  3. Falls back to basic cross-study pooling
- **`study-matched`**: Run DE independently within each GEO study, combine via meta-analysis. Eliminates batch effects entirely.
- **`pooled`**: Pool all samples into one comparison (original behavior). Fast but susceptible to batch effects.

### CLI Usage

```bash
cd scripts/demos

# Auto mode (default) — tries study-matched first, falls back automatically
python -m chatgeo.cli "psoriasis in skin tissue" --verbose

# Explicit study-matched meta-analysis
python -m chatgeo.cli "psoriasis in skin tissue" --mode study-matched --verbose

# Pooled mode (original behavior)
python -m chatgeo.cli "psoriasis in skin tissue" --mode pooled --verbose

# Fisher's method instead of Stouffer's for meta-analysis
python -m chatgeo.cli "psoriasis in skin tissue" --mode study-matched --meta-method fisher

# Require at least 5 matched studies for meta-analysis
python -m chatgeo.cli "psoriasis in skin tissue" --min-studies 5

# Filter controls to match dominant test platform
python -m chatgeo.cli "psoriasis in skin tissue" --platform-filter majority
```

### MCP Server

The MCP server exposes ChatGEO and SPARQL analysis tools for use by AI agents.

#### Available Tools

| Tool | Description | Background? |
|------|-------------|------------|
| `get_sample_metadata` | Study-level breakdown for planning analysis | Yes |
| `differential_expression` | Full DE analysis with mode selection | Yes |
| `find_samples` | Find test/control samples with study breakdown | Yes |
| `get_analysis_result` | Poll background job results | No |
| `enrichment_analysis` | Gene set enrichment via g:Profiler | No |
| `resolve_disease_ontology` | Resolve disease to MONDO IDs | No |
| `gene_disease_paths` | Gene-disease connections via SPARQL | No |
| `gene_neighborhood` | Gene neighborhood queries | No |
| `drug_disease_opposing_expression` | Opposing drug/disease expression | No |

#### Provenance Tracking

Every analysis result includes a `provenance` object documenting:
- Analysis mode used and fallback reason (if auto mode)
- Search patterns and query terms
- Sample IDs and study breakdown
- Platform distribution
- Statistical methods and thresholds
- Meta-analysis parameters (for study-matched mode)

This enables full reproducibility — any result can be regenerated by rerunning with the same parameters and sample IDs.

#### Example: Study-Matched Analysis via MCP

```
1. get_sample_metadata(disease_term="psoriasis", tissue="skin")
   → poll with get_analysis_result → see study breakdown + recommendation

2. differential_expression(query="psoriasis in skin", mode="study-matched")
   → poll with get_analysis_result → see per-study DE + meta-analysis results

3. enrichment_analysis(gene_list=[top genes from step 2])
   → GO, KEGG, Reactome enrichment
```

## Template-based query web application (`web-v2`)

The maintained interface is the **Next.js template-based discovery app** in [`web-v2/`](./web-v2/README.md): query cards on the home page link to slot-driven forms under `/template/{templateId}`, and SPARQL runs against the [FRINK](https://frink.apps.renci.org/) **federation** endpoint. **Below, “template UI” means only the three home-page queries** (see `web-v2/lib/landing/template-meta.ts`): **Datasets by keywords** (`dataset_search`), **Gene-level differential expression per contrast** (`gene_expression_gene_level_de_per_contrast`), and **Datasets for a drug** (`drug_datasets`). Other templates are available at direct `/template/...` URLs and in **[`web-v2/README.md`](./web-v2/README.md)**.

**No longer maintained:** the older **Streamlit** UI under [`web/`](./web/README.md) and the experimental **conversational chat** page at `/chat` inside `web-v2` (natural-language threads, lanes B/C, and `@` commands). Use the template UI and the documented API instead.

For optional **developer / implementation history** of broader GXA work (not specific to the three home-page templates), see [`docs/gene_expression_query_progress.md`](./docs/gene_expression_query_progress.md).

### Home-page templates and slot autocomplete (sources)

Autocomplete calls go through `web-v2` Tool Service routes under `/api/tools/ontology/...` (and Wikidata for drugs). Implementations live beside each route under `web-v2/lib/ontology/`.

| Home-page template | Template id | Slot suggestions (external / API source) |
|--------------------|-------------|-------------------------------------------|
| **Datasets by keywords** | `dataset_search` | **Health condition (MONDO):** OLS via `mondo/search` (`mondo-ols.ts`). **Host species** and **pathogen species:** OLS NCBITaxon via `ncbitaxon/search` (`ncbitaxon-ols.ts`). **Keywords:** free text. Optional **Include MONDO subclasses:** **OLS4 v2 entities** when expanding MONDO IRIs for the SPARQL filter (`mondo-descendants-ols.ts`). |
| **Gene-level differential expression per contrast** | `gene_expression_gene_level_de_per_contrast` | **Gene symbol(s):** **HGNC** REST API via `hgnc/search` (`hgnc-client.ts`). **Organism / taxon:** OLS NCBITaxon via `ncbitaxon/search`. **Tissue (UBERON):** OLS via `uberon/search?source=ols` (OLS branch in `uberon-ubergraph.ts`). **Factor terms** and **disease (EFO):** OLS via `efo/search` (`efo-ols.ts`). |
| **Datasets for a drug** | `drug_datasets` | **Drug name(s):** **Wikidata** via `wikidata/drugs` (`wikidata-client.ts`). |

### Limitations and guardrails

- **Endpoints (three home-page templates):** All runs use the FRINK **federation** SPARQL URL from the WOBD context pack—not the standalone `.../nde/sparql` or `.../gene-expression-atlas-okn/sparql` services. **`dataset_search` (Datasets by keywords)** is scoped to the **NDE** named graph (`graphs: ["nde"]`, `FROM <https://purl.org/okn/frink/kg/nde>` injected with the query). **`gene_expression_gene_level_de_per_contrast`** is scoped to **Gene Expression Atlas** (`graphs: ["gene-expression-atlas-okn"]`, `FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>`). **`drug_datasets` (Datasets for a drug)** uses **`POST /api/tools/drug-datasets`**, which runs separate federated SPARQL steps over **Wikidata** and **NDE** (see `web-v2/lib/dashboard/drug-datasets-plan.ts`). GXA-shaped generated query text still only lengthens the **timeout** on the federated `sparql/execute` call (see below), not the federation base URL.
- **Timeouts:** Default request timeout is 25 seconds (configurable in the context pack). The gene-level GXA template can hit the longer cap (120 s); NDE keyword search (`dataset_search`) may use an intermediate cap (60 s).
- **Result limits:** Maximum `LIMIT` in generated queries and max rows for download are enforced by the context pack (`guardrails.max_limit`, `guardrails.max_rows_download`). Queries that omit `LIMIT` may be capped by the endpoint.
- **Forbidden SPARQL operations:** Write operations are disallowed (INSERT, DELETE, LOAD, CLEAR, DROP, CREATE, MOVE, COPY, ADD). The validator rejects such queries before execution.
- **GEO / GSE in results:** NCBI GEO is not a separate SPARQL graph in FRINK. For **Datasets by keywords**, rows can still show GSE or E-GEOD links when NDE metadata includes those accessions.
- **Context pack:** Full graph lists, extra templates, and guardrails live in [`web-v2/context/packs/wobd.yaml`](./web-v2/context/packs/wobd.yaml). The home page only promotes the three templates above; the template page still shows generated SPARQL (including multi-step output for **`drug_datasets`**).
