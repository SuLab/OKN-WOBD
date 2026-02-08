# OKN-WOBD

Extract data from the [NIAID Data Ecosystem Discovery Portal](https://data.niaid.nih.gov/) and convert for loading into [ProtoOKN](https://www.proto-okn.net/).

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

## Chat UI and query service (web-v2)

The `web-v2` app provides a natural-language chat interface that runs SPARQL against the [FRINK](https://frink.apps.renci.org/) federation and direct endpoints (NDE, Gene Expression Atlas). See `docs/gene_expression_query_progress.md` for implementation status and test questions.

### Limitations and guardrails

- **Endpoints:** Queries run against FRINK. NDE and Gene Expression Atlas (GXA) use **direct endpoints** when the query targets those graphs; other queries use the federated endpoint. Routing is determined by query content (which graph the template used), not by intent metadata.
- **Timeouts:** Default request timeout is 25 seconds (configurable in the context pack). GXA direct requests use a longer timeout (120 s) because that endpoint can be slow.
- **Result limits:** Maximum `LIMIT` in generated queries and max rows for download are enforced by the context pack (`guardrails.max_limit`, `guardrails.max_rows_download`). Queries that omit `LIMIT` may be capped by the endpoint.
- **Forbidden SPARQL operations:** Write operations are disallowed (INSERT, DELETE, LOAD, CLEAR, DROP, CREATE, MOVE, COPY, ADD). The validator rejects such queries before execution.
- **GEO not in FRINK:** NCBI GEO is not loaded as a graph in FRINK. NDE dataset results that have a GSE identifier show links to GEO (and to Expression Atlas via E-GEOD); there is no SPARQL query over GEO data in this app.
- **Graphs and templates:** The WOBD context pack (`web-v2/context/packs/wobd.yaml`) defines default graphs (nde, ubergraph), direct endpoints (nde, gene-expression-atlas-okn), guardrails, and template IDs. User-facing template exposure (e.g. showing the user which query template was used) is planned for a future UI update; meta-coverage and diagrams (Phases 9–10) are deferred until after that.