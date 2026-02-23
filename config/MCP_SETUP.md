# Setting Up OKN MCP Servers for Claude Code

Two remote MCP servers provide biomedical knowledge graph and analysis tools for use within Claude Code sessions.

## Servers

| Server | Description |
|--------|-------------|
| **mcp-proto-okn** | SPARQL query interface to the FRINK federation knowledge graph. Includes schema inspection, ontology-aware queries with automatic descendant expansion, URI lookups, and Mermaid diagram generation. |
| **okn-wobd** | Biomedical analysis tools: gene-disease path finding, gene neighborhood queries, differential expression (ARCHS4), drug-disease opposing expression, g:Profiler enrichment, and MONDO disease ontology resolution. |

## Quick Setup

Add both servers to your Claude Code project settings. From within the project directory, run:

```bash
claude mcp add --transport http mcp-proto-okn http://3.142.249.239/mcp-proto-okn/mcp
claude mcp add --transport http okn-wobd http://3.142.249.239/mcp-wobd/mcp
```

Or manually edit `.claude/settings.local.json` in the project root:

```json
{
  "permissions": {
    "allow": []
  },
  "mcpServers": {
    "mcp-proto-okn": {
      "type": "http",
      "url": "http://3.142.249.239/mcp-proto-okn/mcp"
    },
    "okn-wobd": {
      "type": "http",
      "url": "http://3.142.249.239/mcp-wobd/mcp"
    }
  }
}
```

## Verify

Start a new Claude Code session in the project directory and check that the servers are connected:

```
claude
> /mcp
```

You should see both `mcp-proto-okn` and `okn-wobd` listed with their tools.

## Available Tools

### mcp-proto-okn (Knowledge Graph)

| Tool | Description |
|------|-------------|
| `get_description` | Get knowledge graph metadata (name, PI, funding) |
| `get_schema` | Inspect classes, relationships, and edge properties |
| `query` | Run SPARQL queries with automatic ontology expansion |
| `get_query_template` | Get example SPARQL for edge-property relationships |
| `lookup_uri` | Resolve a term label to its ontology URI |
| `get_descendants` | Expand an ontology URI to all descendant classes |
| `clean_mermaid_diagram` | Clean a Mermaid class diagram for rendering |
| `visualize_schema` | Generate a Mermaid diagram of the KG schema |
| `create_chat_transcript` | Export the conversation as a markdown transcript |

### okn-wobd (Analysis)

| Tool | Description |
|------|-------------|
| `health_check` | Check server status and available capabilities |
| `gene_disease_paths` | Find gene-disease connections across SPOKE, Wikidata, Ubergraph |
| `gene_neighborhood` | Query a gene's neighborhood across FRINK knowledge graphs |
| `drug_disease_opposing_expression` | Find genes with opposing drug/disease expression |
| `differential_expression` | Run DE analysis on ARCHS4 bulk RNA-seq (background job) |
| `find_samples` | Find ARCHS4 test/control samples for a disease |
| `get_sample_metadata` | Get study-level sample metadata for planning DE analysis |
| `enrichment_analysis` | Run g:Profiler enrichment (GO, KEGG, Reactome) |
| `get_analysis_result` | Poll for background job results |
| `resolve_disease_ontology` | Resolve a disease name to MONDO IDs with hierarchy expansion |

## Example Prompts

Once connected, you can ask Claude things like:

- "What genes are associated with pulmonary fibrosis?"
- "Run differential expression analysis for psoriasis in skin tissue"
- "What is the schema of the federation knowledge graph?"
- "Find drugs that have opposing expression to Alzheimer's disease"
- "What are the descendants of rheumatoid arthritis in the MONDO ontology?"
- "Run enrichment analysis on TP53, BRCA1, MYC, and CDK2"

## Notes

- **Long-running tools**: `differential_expression` and `find_samples` run as background jobs. They return a `job_id` immediately — use `get_analysis_result` to poll for completion.
- **Ontology expansion**: The `query` tool in mcp-proto-okn automatically expands ontology URIs (MONDO, HP, GO, etc.) to include descendant concepts. Disable with `auto_expand_descendants=False`.
- **Server availability**: These are development servers. If connections fail, verify the host is reachable: `curl http://3.142.249.239/mcp-proto-okn/mcp`