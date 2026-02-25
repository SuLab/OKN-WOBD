# Setting Up the OKN-WOBD MCP Server for Claude Code

The okn-wobd MCP server provides biomedical analysis tools for use within Claude Code sessions.

## Quick Setup

Add the server to your Claude Code project settings. From within the project directory, run:

```bash
claude mcp add --transport http okn-wobd http://3.142.249.239/mcp-wobd/mcp
```

Or manually edit `.claude/settings.local.json` in the project root:

```json
{
  "permissions": {
    "allow": []
  },
  "mcpServers": {
    "okn-wobd": {
      "type": "http",
      "url": "http://3.142.249.239/mcp-wobd/mcp"
    }
  }
}
```

## Verify

Start a new Claude Code session in the project directory and check that the server is connected:

```
claude
> /mcp
```

You should see `okn-wobd` listed with its tools.

## Available Tools

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
- "Find drugs that have opposing expression to Alzheimer's disease"
- "Run enrichment analysis on TP53, BRCA1, MYC, and CDK2"

## Related Resources

- **[mcp-proto-okn](https://github.com/sbl-sdsc/mcp-proto-okn)** — MCP server for SPARQL queries against the FRINK federation knowledge graph. Provides schema inspection, ontology-aware queries, URI lookups, and diagram generation.

## Notes

- **Long-running tools**: `differential_expression` and `find_samples` run as background jobs. They return a `job_id` immediately — use `get_analysis_result` to poll for completion.
- **Server availability**: This is a development server. If connections fail, verify the host is reachable: `curl http://3.142.249.239/mcp-wobd/mcp`