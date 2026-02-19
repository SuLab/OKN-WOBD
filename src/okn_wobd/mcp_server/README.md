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
| `find_samples` | 5-10 s | ARCHS4 metadata | **yes** |
| `get_sample_metadata` | 30-120 s | ARCHS4 metadata | **yes** |
| `resolve_disease_ontology` | 2-5 s | Ubergraph SPARQL | no |
| `enrichment_analysis` | 2-5 s | g:Profiler REST | no |

### Background jobs

`differential_expression`, `find_samples`, and `get_sample_metadata` dispatch work to a background thread and return a `job_id` immediately. The client polls `get_analysis_result(job_id=...)` every 30-60 seconds until the job completes. This keeps each MCP tool call within the ~60-second client timeout.

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

The SPARQL-based analysis tools (`gene_disease_paths`, `gene_neighborhood`, `drug_disease_opposing_expression`), `resolve_disease_ontology`, and `enrichment_analysis` work without ARCHS4 data.

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

1. Copy `config/mcp-dev.json` to your project-level `.mcp.json` (or merge into your existing Claude Code settings).
2. Edit the paths to match your local checkout.
3. Restart Claude Code. Verify with: `> Use the health_check tool`

### Biomni

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

1. Copy or symlink the config into Biomni's server directory:
   ```bash
   cp config/biomni.yaml /path/to/biomni/servers/okn-wobd.yaml
   ```
2. If running Biomni from a different directory, use absolute paths in the YAML.
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

Any MCP client can connect by URL. The repo includes `config/mcp-remote.json`:

```json
{
  "mcpServers": {
    "okn-wobd": {
      "type": "url",
      "url": "https://your-server:8000/mcp"
    }
  }
}
```

Replace `your-server` with the hostname/IP. That's it — no tokens or extra configuration needed.

If the server was started with `OKN_MCP_API_KEY`, add the auth header:

```json
{
  "mcpServers": {
    "okn-wobd": {
      "type": "url",
      "url": "https://your-server:8000/mcp",
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
- `ARCHS4_DATA_DIR` set in the environment or in `scripts/demos/.env`

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
