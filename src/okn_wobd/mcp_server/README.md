# OKN-WOBD MCP Server

An [MCP](https://modelcontextprotocol.io/) server that exposes biomedical analysis tools for AI assistants (Claude Code, Claude Desktop, Biomni, etc.) to run gene-disease queries, differential expression analyses, and gene-set enrichment without leaving the conversation.

Supports **local** (stdio) and **remote** (Streamable HTTP, SSE) transports. Remote servers work out of the box with no authentication required — any MCP client can connect by URL, just like other public MCP servers. Optional API-key auth is available for restricted deployments.

## Architecture

```
                                  stdio (local)
┌──────────────────────┐  ─── or ────────────────  ┌─────────────────────────┐
│  Claude Code / Biomni│  HTTP (streamable-http)   │  okn_wobd.mcp_server    │
│  or other MCP client │  ─── or ────────────────  │                         │
└──────────────────────┘  SSE   (legacy)           │  server.py   (FastMCP)  │
                                                   │  ├─ health_check        │
                                                   │  ├─ tools_analysis.py   │
                                                   │  │   ├─ gene_disease_paths
                                                   │  │   ├─ gene_neighborhood
                                                   │  │   └─ drug_disease_opposing_expression
                                                   │  └─ tools_chatgeo.py    │
                                                   │      ├─ differential_expression
                                                   │      ├─ get_analysis_result
                                                   │      ├─ find_samples    │
                                                   │      ├─ get_sample_metadata
                                                   │      ├─ resolve_disease_ontology
                                                   │      └─ enrichment_analysis
                                                   └────────┬────────────────┘
                                                            │
                             ┌───────────────┬──────────────┴──────┬────────────────┐
                             ▼               ▼                     ▼                ▼
                        SPOKE/Wikidata    Ubergraph             ARCHS4 (local)   g:Profiler
                        FRINK SPARQL      SPARQL                HDF5 files       REST API
```

The server wraps two packages that live in `scripts/demos/`:

- **analysis_tools** — SPARQL queries against FRINK knowledge graphs (SPOKE-OKN, Wikidata, Ubergraph, GXA).
- **chatgeo** — Differential expression analysis using local ARCHS4 HDF5 files, with g:Profiler enrichment.

## Tools

| Tool | Runtime | Data source | Requires ARCHS4? |
|------|---------|-------------|:-:|
| `health_check` | instant | — | no |
| `gene_disease_paths` | 5-30 s | SPOKE, Wikidata, Ubergraph SPARQL | no |
| `gene_neighborhood` | 5-20 s | FRINK graphs (parallel) | no |
| `drug_disease_opposing_expression` | 15-45 s | GXA in FRINK | no |
| `differential_expression` | 30 s - 5 min | ARCHS4 + g:Profiler | **yes** |
| `get_analysis_result` | instant | polls background job | no |
| `find_samples` | 30-120 s | ARCHS4 metadata + NDE SPARQL | **yes** |
| `get_sample_metadata` | 30-120 s | ARCHS4 metadata | **yes** |
| `resolve_disease_ontology` | 2-5 s | Ubergraph SPARQL | no |
| `enrichment_analysis` | 2-5 s | g:Profiler REST | no |

### Background jobs

`differential_expression`, `find_samples`, and `get_sample_metadata` dispatch work to a background thread and return a `job_id` immediately. The client polls `get_analysis_result(job_id=...)` every 30-60 seconds until the job completes. This keeps each MCP tool call within the ~60-second client timeout.

## Prerequisites

```bash
# 1. Install the core package (from repo root, requires Python >= 3.11)
pip install -e .

# 2. Install demo script dependencies (analysis_tools, chatgeo, clients packages)
pip install SPARQLWrapper h5py scipy numpy            # SPARQL + ARCHS4 tools
pip install pydeseq2 gprofiler-official               # DE analysis + enrichment
pip install anthropic                                  # Optional: LLM interpretation

# 3. The demos directory (scripts/demos/) must exist in the repo —
#    the server adds it to sys.path automatically.

# 4. Copy and configure the .env file
cp .env.example .env
```

Edit `.env`:

| Variable | Required for | Description |
|----------|-------------|-------------|
| `ARCHS4_DATA_DIR` | ChatGEO tools | Path to directory with ARCHS4 HDF5 files (~58 GB each) |
| `ANTHROPIC_API_KEY` | LLM interpretation | Anthropic API key (optional — interpretation is off by default in MCP) |

The SPARQL-based analysis tools (`gene_disease_paths`, `gene_neighborhood`, `drug_disease_opposing_expression`), `resolve_disease_ontology`, and `enrichment_analysis` work without ARCHS4 data — they only need SPARQLWrapper and outbound HTTPS access.

## Tool Reference

### `health_check`

Returns server status and capability flags (analysis_tools, chatgeo, archs4_data, anthropic_api_key). No parameters.

### `gene_disease_paths`

Find connections between a gene and diseases across SPOKE-OKN, Wikidata, and Ubergraph.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gene_symbol` | str | *(required)* | Gene symbol (e.g. `"SFRP2"`, `"BRCA1"`, `"TP53"`) |

Returns: `gene`, `total_connections`, `connections` list (each with `disease_name`, `path_type`, `source`), `summary` (counts by source and path type).

### `gene_neighborhood`

Query the immediate neighborhood of a gene across FRINK knowledge graphs (SPOKE-OKN, SPOKE-GeneLab, Wikidata, NDE, BioBricks-AOPWiki).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gene_symbol` | str | `None` | Gene symbol (e.g. `"CD19"`) |
| `ncbi_gene_id` | str | `None` | NCBI Gene ID (e.g. `"930"`) |
| `limit` | int | `10` | Max entities per graph |
| `timeout` | int | `30` | Per-graph SPARQL timeout (seconds) |

At least one of `gene_symbol` or `ncbi_gene_id` is required. Returns: `gene_symbol`, `gene_iri`, `graphs` (per-graph entity lists).

### `drug_disease_opposing_expression`

Find genes with opposing expression between drug treatment and disease in GXA data.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug_direction` | str | `"down"` | Direction of drug effect (`"up"` or `"down"`) |
| `disease_direction` | str | `"up"` | Direction of disease effect (`"up"` or `"down"`) |
| `drug_fc_threshold` | float | `2.0` | Absolute log2 FC threshold for drug |
| `disease_fc_threshold` | float | `1.5` | Absolute log2 FC threshold for disease |
| `pvalue_threshold` | float | `0.05` | Adjusted p-value threshold |
| `limit` | int | `500` | Max drug-gene pairs from SPARQL |
| `max_results` | int | `50` | Max results returned (sorted by disease FC) |

Returns: `results` list (gene, drug/disease study details, fold changes), `summary` (unique genes/diseases/drugs).

### `differential_expression`

Run differential expression analysis for a disease condition using ARCHS4 bulk RNA-seq. **Background job** — returns `job_id` immediately.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | *(required)* | Natural language query (e.g. `"psoriasis in skin tissue"`) |
| `disease` | str | `None` | Override parsed disease term |
| `tissue` | str | `None` | Override/specify tissue constraint |
| `species` | str | `"human"` | `"human"`, `"mouse"`, or `"both"` |
| `method` | str | `"mann-whitney"` | `"mann-whitney"`, `"welch-t"`, or `"deseq2"` |
| `fdr_threshold` | float | `0.01` | FDR significance threshold |
| `log2fc_threshold` | float | `2.0` | Log2 fold-change threshold |
| `max_test_samples` | int | `100` | Max test samples |
| `max_control_samples` | int | `100` | Max control samples |
| `mode` | str | `"auto"` | `"auto"`, `"pooled"`, or `"study-matched"` |
| `meta_method` | str | `"stouffer"` | Meta-analysis method: `"stouffer"` or `"fisher"` |
| `min_studies` | int | `3` | Min matched studies for study-matched mode |

Analysis modes:
- **auto** (default): Tries study-matched meta-analysis first, falls back to study-prioritized pooling, then basic pooling.
- **study-matched**: Per-study DE + Stouffer/Fisher meta-analysis. Best for eliminating batch effects.
- **pooled**: Cross-study pooling. Fast but susceptible to batch effects.

Result (via `get_analysis_result`): `sample_discovery`, `de_results` (with `significant_genes` list), `enrichment`, `provenance`.

### `get_analysis_result`

Poll for the result of a background job.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `job_id` | str | *(required)* | Job ID from `differential_expression`, `find_samples`, or `get_sample_metadata` |

Returns: `status` (`"running"`, `"completed"`, or `"error"`), `result` (when completed), `elapsed_seconds` (when running).

### `find_samples`

Find ARCHS4 test and control samples for a disease condition. **Background job** — returns `job_id` immediately.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `disease_term` | str | *(required)* | Disease or condition (e.g. `"psoriasis"`) |
| `tissue` | str | `None` | Tissue constraint (e.g. `"skin"`) |
| `max_test_samples` | int | `100` | Max test samples |
| `max_control_samples` | int | `100` | Max control samples |
| `use_ontology` | bool | `True` | Use MONDO ontology-enhanced search via NDE |

Result (via `get_analysis_result`): sample counts, study lists, `study_breakdown` (per-study counts, platform distribution, mode recommendation), `ontology_discovery` details.

### `get_sample_metadata`

Get study-level sample metadata for planning DE analysis. **Background job** — returns `job_id` immediately. Use this **before** `differential_expression` to check data availability.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `disease_term` | str | *(required)* | Disease or condition (e.g. `"psoriasis"`) |
| `tissue` | str | `None` | Tissue constraint (e.g. `"skin"`) |
| `max_samples` | int | `500` | Max samples to consider |
| `use_ontology` | bool | `True` | Use ontology-enhanced search |

Result (via `get_analysis_result`): sample counts, `study_breakdown`, `recommendation` (`"study-matched"` or `"pooled"`), `recommendation_reason`.

### `resolve_disease_ontology`

Resolve a disease name to MONDO IDs and expand via ontology hierarchy. Does **not** require ARCHS4.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `disease_name` | str | *(required)* | Disease name (e.g. `"atherosclerosis"`) |
| `expand` | bool | `True` | Expand via ontology hierarchy |
| `max_terms` | int | `50` | Max terms in expansion |

Returns: `mondo_ids`, `labels`, `confidence`, `expansion` (with `expanded_ids` and `labels`).

### `enrichment_analysis`

Run gene-set enrichment via g:Profiler (GO, KEGG, Reactome). Does **not** require ARCHS4.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gene_list` | list[str] | *(required)* | Gene symbols (e.g. `["TP53", "BRCA1", "MYC"]`) |
| `organism` | str | `"hsapiens"` | Organism identifier |
| `sources` | list[str] | `["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"]` | Enrichment databases |
| `threshold` | float | `0.05` | P-value significance threshold |

Returns: `input_genes`, `genes_mapped`, `total_terms`, `by_source` (term lists per database with `term_id`, `term_name`, `p_value`, `genes`).

## Example Workflows

### Workflow 1: Explore a gene's disease connections

```
User: What diseases are connected to SFRP2?

→ gene_disease_paths(gene_symbol="SFRP2")
  Returns connections from SPOKE, Wikidata, Ubergraph

→ gene_neighborhood(gene_symbol="SFRP2")
  Returns related entities across all FRINK graphs
```

### Workflow 2: Differential expression analysis

```
User: Find genes differentially expressed in psoriasis skin tissue

→ get_sample_metadata(disease_term="psoriasis", tissue="skin")
  Returns job_id, poll with get_analysis_result
  Result: 45 test samples, 120 controls, 8 studies with both
  Recommendation: "study-matched"

→ differential_expression(
      query="psoriasis in skin tissue",
      mode="study-matched",
      method="mann-whitney"
  )
  Returns job_id, poll with get_analysis_result (30-60s)
  Result: 200 significant genes, enrichment in immune pathways

→ enrichment_analysis(gene_list=["IL17A", "IL22", "S100A7", ...])
  Deeper enrichment on the top DE genes
```

### Workflow 3: Drug repurposing candidates

```
User: Find drugs that might counteract gene expression changes in disease

→ drug_disease_opposing_expression(
      drug_direction="down",
      disease_direction="up"
  )
  Returns genes where drugs suppress pathologically elevated expression

→ gene_disease_paths(gene_symbol="<top hit gene>")
  Investigate the disease connections of promising targets
```

### Workflow 4: Ontology-driven sample discovery

```
User: What MONDO terms map to atherosclerosis?

→ resolve_disease_ontology(disease_name="atherosclerosis")
  Returns MONDO IDs, subtypes (coronary, peripheral, etc.)

→ find_samples(disease_term="atherosclerosis", tissue="artery")
  Discovers samples via both keyword matching and MONDO annotations in NDE
```

## Transports

The server supports three transports, selected via the `OKN_MCP_TRANSPORT` environment variable:

| Transport | Value | Use case |
|-----------|-------|----------|
| **stdio** (default) | `stdio` | Local — client spawns the server as a subprocess |
| **Streamable HTTP** | `streamable-http` | Remote — recommended for remote/networked access |
| **SSE** | `sse` | Remote — legacy Server-Sent Events transport |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OKN_MCP_TRANSPORT` | `stdio` | Transport: `stdio`, `streamable-http`, or `sse` |
| `OKN_MCP_HOST` | `0.0.0.0` | Bind address (HTTP transports only) |
| `OKN_MCP_PORT` | `8000` | Listen port (HTTP transports only) |
| `OKN_MCP_API_KEY` | *(none)* | If set, requires `Authorization: Bearer <key>` on all HTTP requests |
| `OKN_MCP_LOG_FILE` | `~/.okn_wobd/mcp_server.log` | Log file path |
| `OKN_MCP_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Usage: Local (stdio)

### Claude Code

Add the server to your Claude Code MCP configuration. The repo includes a template at `config/mcp-dev.json`:

```json
{
  "mcpServers": {
    "okn-wobd": {
      "command": "python3.11",
      "args": ["-m", "okn_wobd.mcp_server"],
      "cwd": "/path/to/OKN-WOBD",
      "env": {
        "PYTHONPATH": "/path/to/OKN-WOBD/src"
      }
    }
  }
}
```

1. Copy `config/mcp-dev.json` to your project-level `.mcp.json` (or merge into your existing Claude Code settings).
2. Replace `/path/to/OKN-WOBD` with the absolute path to your checkout (both `cwd` and `PYTHONPATH`).
3. Restart Claude Code. Verify with: `> Use the health_check tool`

### Biomni

[Biomni](https://github.com/lhallee/Biomni) discovers MCP servers from YAML config files. The repo includes a template at `config/biomni.yaml`:

```yaml
name: okn-wobd
description: >
  Biomedical analysis tools for gene-disease path finding, gene neighborhood
  queries, drug-disease opposing expression patterns, and differential
  expression analysis via ARCHS4.
transport: stdio
command: python3.11
args:
  - "-m"
  - okn_wobd.mcp_server
cwd: /path/to/OKN-WOBD
env:
  PYTHONPATH: /path/to/OKN-WOBD/src
```

1. Copy or symlink the config into Biomni's server directory:
   ```bash
   cp config/biomni.yaml /path/to/biomni/servers/okn-wobd.yaml
   ```
2. Replace `/path/to/OKN-WOBD` with the absolute path to your checkout (both `cwd` and `PYTHONPATH`).
3. Start Biomni. The OKN-WOBD tools will be registered automatically.

## Usage: Remote (HTTP)

### Starting the server

```bash
# Streamable HTTP on default port 8000 (open access, no auth)
OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp

# Custom port
OKN_MCP_PORT=9000 OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp

# SSE transport (legacy)
OKN_MCP_TRANSPORT=sse okn-wobd-mcp
```

The server will print its listen address to stderr and begin accepting connections. By default there is no authentication — any MCP client can connect, just like other public-facing MCP servers.

To optionally require a Bearer token, set `OKN_MCP_API_KEY`:

```bash
OKN_MCP_API_KEY=my-secret-key OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp
```

### Connecting from Claude Code

Any MCP client can connect by URL. The repo includes a template at `config/mcp-remote.json`:

```json
{
  "mcpServers": {
    "okn-wobd": {
      "type": "url",
      "url": "https://your-server-host:port/mcp"
    }
  }
}
```

Replace `your-server-host` and `port` to match your deployment (e.g. `https://mcp.example.com:8000/mcp`). The port must match the `OKN_MCP_PORT` value the server was started with (default 8000).

If the server was started with `OKN_MCP_API_KEY`, add the auth header:

```json
{
  "mcpServers": {
    "okn-wobd": {
      "type": "url",
      "url": "https://your-server-host:port/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### MCP endpoint paths

| Transport | Endpoint |
|-----------|----------|
| Streamable HTTP | `POST /mcp` |
| SSE | `GET /sse` (stream) + `POST /messages/` (client→server) |

## Public deployment

To expose the server on the internet, you need to address several concerns beyond just starting the HTTP transport.

### 1. TLS termination

MCP clients expect HTTPS for remote servers. Use a reverse proxy to terminate TLS:

**nginx** (minimal example):
```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;

    ssl_certificate     /etc/letsencrypt/live/mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;            # required for SSE/streaming
        proxy_read_timeout 600s;        # long-running tools
    }
}
```

Or use **Caddy** for automatic Let's Encrypt:
```
mcp.example.com {
    reverse_proxy 127.0.0.1:8000 {
        flush_interval -1    # disable buffering for SSE
    }
}
```

### 2. Authentication (optional)

The server runs open by default — no tokens required. This is the simplest setup and matches the pattern of most public MCP servers.

If you want to restrict access, set `OKN_MCP_API_KEY` to require a Bearer token. The built-in middleware validates `Authorization: Bearer <key>` on every request, returning 401 for missing/wrong keys.

Other optional hardening:
- Rate limiting at the reverse proxy layer
- IP allowlisting if clients have known addresses
- OAuth 2.0 via the MCP SDK's built-in auth provider support

### 3. ARCHS4 data

The ChatGEO tools (`differential_expression`, `find_samples`, `get_sample_metadata`) require local access to ARCHS4 HDF5 files (~58 GB each). The server machine must have:
- Sufficient disk space for the HDF5 files
- `ARCHS4_DATA_DIR` set in the environment or in `.env`

The SPARQL-based tools and `enrichment_analysis` work without local data and only make outbound HTTP requests.

### 4. Resource requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Disk | ~120 GB (2 ARCHS4 HDF5 files) | 200 GB+ (room for logs, cache) |
| RAM | 4 GB | 8 GB+ (HDF5 reads are memory-mapped) |
| CPU | 2 cores | 4+ cores (parallel SPARQL queries, DE analysis) |
| Network | Outbound HTTPS to SPARQL endpoints + g:Profiler | — |

### 5. Quick tunnel for testing

For quick remote testing without a public server, use a tunnel:

```bash
# Start the server
OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp

# In another terminal — ngrok
ngrok http 8000
# → https://abc123.ngrok.io

# Or Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```

Then point your remote Claude Code config at the tunnel URL:
```json
{
  "mcpServers": {
    "okn-wobd": {
      "type": "url",
      "url": "https://abc123.ngrok.io/mcp"
    }
  }
}
```

### 6. Process management

For long-running deployments, use a process manager:

```bash
# systemd service (Linux)
# /etc/systemd/system/okn-wobd-mcp.service
[Unit]
Description=OKN-WOBD MCP Server
After=network.target

[Service]
User=okn
WorkingDirectory=/opt/OKN-WOBD
Environment=OKN_MCP_TRANSPORT=streamable-http
Environment=OKN_MCP_API_KEY=<your-key>
Environment=ARCHS4_DATA_DIR=/data/archs4
ExecStart=/opt/OKN-WOBD/venv/bin/okn-wobd-mcp
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Running directly

You can start the server manually for testing:

```bash
# stdio (default)
python3.11 -m okn_wobd.mcp_server
okn-wobd-mcp

# HTTP
OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp
```

In stdio mode the server reads JSON-RPC from stdin and writes responses to stdout — the MCP client handles the protocol. In HTTP mode it starts a uvicorn server and logs to stderr.

## Logging

The server writes structured logs to a rotating file.

| Setting | Default | Override |
|---------|---------|----------|
| Log file | `~/.okn_wobd/mcp_server.log` | `OKN_MCP_LOG_FILE` env var |
| Log level | `INFO` | `OKN_MCP_LOG_LEVEL` env var |
| Rotation | 5 MB, 3 backups | — |
| Logger name | `okn_wobd.mcp_server` | — |

The log captures:

- **Server lifecycle** — startup with version, transport type, host/port
- **Tool invocations** — every tool call with key arguments (INFO)
- **Background jobs** — dispatch, thread start, completion with elapsed time and result summary, errors with tracebacks
- **Auth events** — API-key middleware activation (INFO)
- **Errors** — all caught exceptions with context (ERROR)
- **Poll requests** — `get_analysis_result` polls (DEBUG)

To watch logs in real time:

```bash
tail -f ~/.okn_wobd/mcp_server.log
```

## Tests

```bash
# Unit tests (mocked, no network or ARCHS4 needed)
python3.11 -m pytest tests/test_mcp_server.py tests/test_mcp_analysis_tools.py tests/test_mcp_chatgeo_tools.py -v

# Live integration tests (hits real SPARQL endpoints and g:Profiler)
RUN_INTEGRATION_TESTS=1 python3.11 -m pytest tests/test_mcp_integration.py -v
```
