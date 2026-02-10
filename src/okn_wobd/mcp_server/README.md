# OKN-WOBD MCP Server

An [MCP](https://modelcontextprotocol.io/) server that exposes biomedical analysis tools over the stdio transport. It lets AI assistants (Claude Code, Claude Desktop, Biomni, etc.) run gene-disease queries, differential expression analyses, and gene-set enrichment without leaving the conversation.

## Architecture

```
┌──────────────────────┐  stdio (JSON-RPC)  ┌─────────────────────────┐
│  Claude Code / Biomni│ ◄────────────────► │  okn_wobd.mcp_server    │
└──────────────────────┘                    │                         │
                                            │  server.py   (FastMCP)  │
                                            │  ├─ health_check        │
                                            │  ├─ tools_analysis.py   │
                                            │  │   ├─ gene_disease_paths
                                            │  │   ├─ gene_neighborhood
                                            │  │   └─ drug_disease_opposing_expression
                                            │  └─ tools_chatgeo.py    │
                                            │      ├─ differential_expression
                                            │      ├─ get_analysis_result
                                            │      ├─ find_samples    │
                                            │      └─ enrichment_analysis
                                            └────────┬────────────────┘
                                                     │
                              ┌───────────────┬──────┴──────┬────────────────┐
                              ▼               ▼             ▼                ▼
                         SPOKE/Wikidata    Ubergraph     ARCHS4 (local)   g:Profiler
                         FRINK SPARQL      SPARQL        HDF5 files       REST API
```

The server wraps two packages that live in `scripts/demos/`:

- **analysis_tools** — SPARQL queries against FRINK knowledge graphs (SPOKE-OKN, Wikidata, Ubergraph, GXA).
- **chatgeo** — Differential expression analysis using local ARCHS4 HDF5 files, with g:Profiler enrichment.

MCP uses stdout for its JSON-RPC channel, so the server redirects all tool `print()` output to stderr and writes logs to a dedicated file (see [Logging](#logging) below).

## Tools

| Tool | Runtime | Data source | Requires ARCHS4? |
|------|---------|-------------|:-:|
| `health_check` | instant | — | no |
| `gene_disease_paths` | 5-30 s | SPOKE, Wikidata, Ubergraph SPARQL | no |
| `gene_neighborhood` | 5-20 s | FRINK graphs (parallel) | no |
| `drug_disease_opposing_expression` | 15-45 s | GXA in FRINK | no |
| `differential_expression` | 30 s - 5 min | ARCHS4 + g:Profiler | **yes** |
| `get_analysis_result` | instant | polls background job | no |
| `find_samples` | 5-10 s | ARCHS4 metadata | **yes** |
| `enrichment_analysis` | 2-5 s | g:Profiler REST | no |

### Background jobs

`differential_expression` dispatches all methods (mann-whitney, welch-t, deseq2) to a background thread and returns a `job_id` immediately. The client polls `get_analysis_result(job_id=...)` every 30-60 seconds until the job completes. This keeps each MCP tool call within the ~60-second client timeout.

## Prerequisites

```bash
# 1. Install the package (from repo root)
pip install -e .

# 2. The demos directory (scripts/demos/) must exist in the repo —
#    the server adds it to sys.path automatically.

# 3. Copy and configure the demos .env file
cp scripts/demos/.env.example scripts/demos/.env
```

Edit `scripts/demos/.env`:

| Variable | Required for | Description |
|----------|-------------|-------------|
| `ARCHS4_DATA_DIR` | ChatGEO tools | Path to directory with ARCHS4 HDF5 files (~58 GB each) |
| `ANTHROPIC_API_KEY` | LLM interpretation | Anthropic API key (optional — interpretation is off by default in MCP) |

The three SPARQL-based analysis tools (`gene_disease_paths`, `gene_neighborhood`, `drug_disease_opposing_expression`) and `enrichment_analysis` work without ARCHS4 data.

## Usage with Claude Code

Add the server to your Claude Code MCP configuration. The repo includes a ready-made config at `config/mcp-dev.json`:

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

To use it:

1. Copy `config/mcp-dev.json` to your Claude Code settings directory (or merge into your existing MCP config):
   ```bash
   # macOS / Linux
   cp config/mcp-dev.json ~/.claude/claude_desktop_config.json

   # Or add to the project-level config
   cp config/mcp-dev.json .mcp.json
   ```

2. Edit the paths to match your local checkout.

3. Restart Claude Code. The tools will appear in the tool list. You can verify with:
   ```
   > Use the health_check tool
   ```

Claude Code will then be able to call tools like `gene_disease_paths(gene_symbol="TP53")` or `differential_expression(query="psoriasis in skin tissue")` directly in conversation.

## Usage with Biomni

[Biomni](https://github.com/lhallee/Biomni) discovers MCP servers from YAML config files. The repo includes `config/biomni.yaml`:

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
env:
  PYTHONPATH: src
```

To use it:

1. Copy or symlink the config into Biomni's server directory:
   ```bash
   cp config/biomni.yaml /path/to/biomni/servers/okn-wobd.yaml
   ```

2. Make sure `PYTHONPATH` resolves correctly. If running Biomni from a different directory, use absolute paths:
   ```yaml
   env:
     PYTHONPATH: /path/to/OKN-WOBD/src
   ```
   and add:
   ```yaml
   cwd: /path/to/OKN-WOBD
   ```

3. Start Biomni. The OKN-WOBD tools will be registered automatically.

## Running directly

You can also start the server manually for testing:

```bash
# Via module
python3.11 -m okn_wobd.mcp_server

# Via installed script
okn-wobd-mcp
```

The server reads JSON-RPC from stdin and writes responses to stdout. In practice you won't interact with it directly — the MCP client (Claude Code, Biomni) handles the protocol.

## Logging

The server writes structured logs to a file (not stdout/stderr, which would interfere with the MCP JSON-RPC channel).

| Setting | Default | Override |
|---------|---------|----------|
| Log file | `~/.okn_wobd/mcp_server.log` | `OKN_MCP_LOG_FILE` env var |
| Log level | `INFO` | `OKN_MCP_LOG_LEVEL` env var |
| Rotation | 5 MB, 3 backups | — |
| Logger name | `okn_wobd.mcp_server` | — |

The log captures:

- **Server lifecycle** — startup with version info
- **Tool invocations** — every tool call with key arguments (INFO)
- **Background jobs** — dispatch, thread start, completion with elapsed time and result summary, errors with tracebacks
- **Errors** — all caught exceptions with context (ERROR)
- **Poll requests** — `get_analysis_result` polls (DEBUG)

Example log output:

```
2026-02-09 14:23:01,234 okn_wobd.mcp_server.server INFO MCP server starting (version 0.1.0)
2026-02-09 14:23:15,891 okn_wobd.mcp_server.tools_analysis INFO gene_disease_paths called: gene=TP53
2026-02-09 14:24:02,456 okn_wobd.mcp_server.tools_chatgeo INFO differential_expression called: query='psoriasis in skin tissue', method=mann-whitney
2026-02-09 14:24:02,789 okn_wobd.mcp_server.tools_chatgeo INFO Dispatched background job a1b2c3d4 (disease=psoriasis, tissue=skin, method=mann-whitney)
2026-02-09 14:24:02,790 okn_wobd.mcp_server.tools_chatgeo INFO Background job a1b2c3d4 started (disease=psoriasis, method=mann_whitney_u)
2026-02-09 14:24:48,123 okn_wobd.mcp_server.tools_chatgeo INFO Background job a1b2c3d4 completed in 45.3s (127 significant genes)
```

To watch logs in real time:

```bash
tail -f ~/.okn_wobd/mcp_server.log
```

To enable DEBUG level (includes poll requests):

```bash
export OKN_MCP_LOG_LEVEL=DEBUG
```

## Tests

```bash
# Unit tests (mocked, no network or ARCHS4 needed)
python3.11 -m pytest tests/test_mcp_server.py tests/test_mcp_analysis_tools.py tests/test_mcp_chatgeo_tools.py -v

# Live integration tests (hits real SPARQL endpoints and g:Profiler)
RUN_INTEGRATION_TESTS=1 python3.11 -m pytest tests/test_mcp_integration.py -v
```
