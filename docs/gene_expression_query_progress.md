# Gene expression query support – implementation progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | GXA DE shape & contrast modeling (`docs/gxa_shape.md`) | Done |
| 1 | Dataset discovery & expression-aware coverage (web-v2 templates + wiring) | Done |
| 2 | Dataset ↔ gene bridge (contrast-aware genes-in-dataset, datasets-for-gene) | Done |
| 3 | Cross-dataset comparison (aggregation, agreement/discordance) | Done |
| 4 | Contextual queries (ontology-grounded filters) | Pending |
| 5 | Evidence-centric UI (contrast labels, “why am I seeing this?”) | Pending |
| 6 | Meta-coverage / observatory queries | Pending |
| 7 | Limitations & guardrails (README, context pack) | Pending |

Last updated: Phase 3 cross-dataset templates added (summary, agreement, discordance).

---

## Phase 1 – what to test before continuing

Run these with the web-v2 dev server: `cd web-v2 && npm run dev` (default http://localhost:3000). Use `http://localhost:3000` in the curls if your port differs.

### 1. Intent classification

Check that “gene expression dataset” questions get task `gene_expression_dataset_search`:

```bash
# First, verify the endpoint returns JSON (check for errors)
curl -s -X POST http://localhost:3000/api/tools/nl/intent \
  -H "Content-Type: application/json" \
  -d '{"text": "What gene expression datasets exist?", "pack_id": "wobd"}' | jq '.'

# Then check just the task field
curl -s -X POST http://localhost:3000/api/tools/nl/intent \
  -H "Content-Type: application/json" \
  -d '{"text": "What gene expression datasets exist?", "pack_id": "wobd"}' | jq '.task'
```

**Expected:** Full JSON response with `task: "gene_expression_dataset_search"`. 

**Important:** For `gene_expression_dataset_search`, the intent route now sets `intent.graphs = ["gene-expression-atlas-okn"]` so the execute route injects only the GXA FROM and, after stripping it, sends a query with no FROM (default graph) to the direct GXA endpoint. Without this, default graphs `["nde", "ubergraph"]` were injected and the GXA endpoint received `FROM nde` / `FROM ubergraph`, returning 0 results.

**If you get nothing/empty:** 
- Check if the dev server is running (`cd web-v2 && npm run dev`)
- Check server terminal for errors
- Try a simpler test: `curl -s -X POST http://localhost:3000/api/tools/nl/intent -H "Content-Type: application/json" -d '{"text": "find datasets", "pack_id": "wobd"}' | jq '.task'` (should return `"dataset_search"`)

### 2. SPARQL generation

With that intent, check that the template produces the GXA coverage query:

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent \
  -H "Content-Type: application/json" \
  -d '{"text": "What gene expression datasets exist?", "pack_id": "wobd"}' > /tmp/intent.json

curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d "{\"intent\": $(cat /tmp/intent.json), \"pack_id\": \"wobd\"}" | jq -r '.query'
```

**Expected:** SPARQL containing `FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>`, `GROUP BY ?experimentId`, and selects `experimentId`, `contrastCount`, `sampleContrastLabel`.

### 3. Execute the query

Run the generated query through the app. The executor detects GXA in the query and routes to the direct endpoint (`gene-expression-atlas-okn` in `direct_endpoints`); it strips the FROM clause before sending.

```bash
# Run all three commands in order (step 3 = the last curl; it needs QUERY from the middle curl)
curl -s -X POST http://localhost:3000/api/tools/nl/intent \
  -H "Content-Type: application/json" \
  -d '{"text": "What gene expression datasets exist?", "pack_id": "wobd"}' > /tmp/intent.json
QUERY=$(curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d "{\"intent\": $(cat /tmp/intent.json), \"pack_id\": \"wobd\"}" | jq -r '.query')
curl -s -X POST http://localhost:3000/api/tools/sparql/execute \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(echo "$QUERY" | jq -Rs .), \"pack_id\": \"wobd\"}" | jq '{ bindings_count: (.result.results.bindings | length), first: .result.results.bindings[0], endpoint_used: .endpoint_used }'
```

Check `endpoint_used` in the response: it should be `https://frink.apps.renci.org/gene-expression-atlas-okn/sparql` when GXA is detected. If it shows the federation URL, routing did not trigger.

**Expected:** Non-empty bindings; first row has `experimentId`, `contrastCount`, and optionally `sampleContrastLabel`. The GXA direct endpoint can take 1–2 minutes; the executor uses a 120s timeout for GXA requests.

**If you get `0` and `null`:** Verify the direct endpoint is reachable (query has no FROM):

```bash
# Direct GXA endpoint (no FROM)
curl -s -X POST https://frink.apps.renci.org/gene-expression-atlas-okn/sparql \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX biolink: <https://w3id.org/biolink/vocab/>
SELECT ?experimentId (COUNT(DISTINCT ?contrast) AS ?contrastCount) (SAMPLE(?contrastLabel) AS ?sampleContrastLabel)
WHERE {
  ?association a biolink:GeneExpressionMixin ; biolink:subject ?contrast .
  ?contrast a biolink:Assay .
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
  FILTER(REGEX(STR(?contrast), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))
}
GROUP BY ?experimentId
ORDER BY DESC(?contrastCount)
LIMIT 10' | jq '.results.bindings | length, .[0]'
```


### 4. End-to-end in the UI

In the chat UI, ask: **“What gene expression datasets exist?”** or **“List gene expression experiments.”**

**Expected:** A results table with columns like experiment ID, contrast count, and sample contrast label (no error and no fallback to a different template).

If 1–3 pass, Phase 1 is good to go. If the federation returns no rows in (3), that’s an environment/data issue, not a Phase 1 bug.

---

## Phase 2 – dataset ↔ gene bridge (initial templates)

For Phase 2 we add **two GXA templates** that expose contrast-aware DE results:

- **`gene_expression_genes_in_experiment`** – given an experiment accession (e.g. `E-GEOD-23301`), list DE genes per contrast with `log2fc`, `adjPValue`, and contrast labels.
- **`gene_expression_experiments_for_gene`** – given gene symbols (e.g. `DUSP2`), list experiments/contrasts where the gene is DE with `log2fc`, `adjPValue`, and contrast labels.

These are wired as templates in `web-v2` but not yet exposed via NL intent classification; for now we test them by calling `/api/tools/nl/intent-to-sparql` directly with a crafted intent.

### 1. Genes in a given experiment (per contrast)

Example: **“DE genes in E-GEOD-23301 (any direction)”**.

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_genes_in_experiment",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {
        "experiment_id": "E-GEOD-23301",
        "limit": 50
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

**Expected SPARQL shape:** FROM `gene-expression-atlas-okn`, selects `experimentId`, `contrast`, `contrastId`, `contrastLabel`, `gene`, `geneSymbol`, `log2fc`, `adjPValue`, filtered to `E-GEOD-23301`.

To execute:

```bash
QUERY=$(curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_genes_in_experiment",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {
        "experiment_id": "E-GEOD-23301",
        "limit": 50
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query')

curl -s -X POST http://localhost:3000/api/tools/sparql/execute \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(echo \"$QUERY\" | jq -Rs .), \"pack_id\": \"wobd\", \"mode\": \"federated\", \"graphs\": [\"gene-expression-atlas-okn\"]}" \
  | jq '{count: (.result.results.bindings | length), first: .result.results.bindings[0], endpoint_used: .endpoint_used}'
```

**Expected:** non‑empty bindings with `experimentId = "E-GEOD-23301"`, `contrastId` in `{g1_g2,g1_g3,g1_g4}`, gene symbols, `log2fc`, and optionally `adjPValue`. `endpoint_used` should be the GXA direct endpoint.

**Quick test:** `./scripts/test_gxa_genes_in_experiment.sh` (requires dev server running).

**Note:** `adj_p_value` is optional in the template; some endpoints may omit it. If you previously saw 0 results, this was likely because the FRINK endpoint’s data did not include `adj_p_value` for all associations.

### 2. Experiments/contrasts for a gene

Example: **“Where is DUSP2 upregulated?”** (template only, no NL routing yet).

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_experiments_for_gene",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {
        "gene_symbols": "DUSP2",
        "direction": "up",
        "limit": 50
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

Then execute as above via `/api/tools/sparql/execute` with `mode: "federated"` and `graphs: ["gene-expression-atlas-okn"]`.

**Expected:** rows with `geneSymbol = "DUSP2"` (case‑insensitive), `log2fc > 0`, plus `experimentId`, `contrastId`, and `contrastLabel`. Again, `endpoint_used` should be the GXA direct endpoint.

---

## Phase 3 – cross-dataset comparison

Phase 3 adds **three GXA templates** for cross-dataset aggregation, agreement, and discordance:

- **`gene_expression_gene_cross_dataset_summary`** – For a gene, list all DE evidence across experiments (per contrast) with direction (up/down).
- **`gene_expression_genes_agreement`** – Genes DE in the same direction across ≥ N experiments (default 2). Optional `direction`: "up" or "down".
- **`gene_expression_genes_discordance`** – Genes DE up in some contrasts and down in others.

### 1. Gene cross-dataset summary

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_gene_cross_dataset_summary",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {"gene_symbol": "DUSP2", "limit": 50}
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

Execute via `/api/tools/sparql/execute` with `mode: "federated"` and `graphs: ["gene-expression-atlas-okn"]`.

### 2. Genes agreement (same direction across experiments)

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_genes_agreement",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {"min_experiments": 2, "direction": "up", "limit": 50}
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

### 3. Genes discordance (opposite directions)

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_genes_discordance",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {"limit": 50}
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

**Quick test:** `./scripts/test_gxa_phase3.sh` (requires dev server running).

**Note:** Discordance was fixed by using `removeFromClauses` for GXA direct routing (instead of a custom regex) and simplifying the query (no DISTINCT/ORDER BY).
