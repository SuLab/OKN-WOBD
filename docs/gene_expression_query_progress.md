# Gene expression query support – implementation progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | GXA DE shape & contrast modeling (`docs/gxa_shape.md`) | Done |
| 1 | Dataset discovery & expression-aware coverage (web-v2 templates + wiring) | Done |
| 2 | Dataset ↔ gene bridge (contrast-aware genes-in-dataset, datasets-for-gene) | Done |
| 3 | Cross-dataset comparison (aggregation, agreement/discordance) | Done |
| 4 | Contextual queries (ontology-grounded filters) | Done |
| 5 | NL routing & slot filling for GXA (all tasks + Phase 4 filters from chat) | Done |
| 5a | GEO/GXA sample metadata (chained API or link to GXA) | Done |
| 6 | Evidence-centric UI: requirements for new workflow + minimal current-UI (contrast labels) | Done |
| 7 | NDE↔GXA bridge (link NDE datasets to GXA expression data via GSE↔E-GEOD) | Done |
| 8 | Limitations & guardrails (README, context pack) | Done |
| 9 | Meta-coverage / observatory queries | Future (after UI update) |
| 10 | Diagrams (structured SPARQL output → frontend charting library) | Future (after UI update) |

Last updated: Phase 8 complete (limitations & guardrails in README and pack). Phases 9–10 deferred until after UI update (e.g. expose template to user).

---

## Next steps and future work

| Step | Description | Status |
|------|-------------|--------|
| **Phase 8** | Limitations & guardrails: document in README and context pack | **Done** |
| **Phase 9** | Meta-coverage / observatory queries | **Future:** after UI update (e.g. expose template to user) |
| **Phase 10** | Diagrams: SPARQL output → frontend charting | **Future:** after UI update |
| Optional | Spot-check all GXA tasks + NDE "datasets about X that contain gene expression data" in chat UI | Ready to run |
| Optional | Confirm Phase 4 filters from chat when `allow_open_nl2sparql` is on | Pending |

---

## Build plan evaluation

### Where we are

| Phase | Status | Notes |
|-------|--------|-------|
| 0–5, 5a | Done | Shape, dataset discovery, gene bridge, cross-dataset, ontology filters, NL routing, metadata links |
| **6** | Done | Evidence-centric: requirements doc + contrast labels wrap in table |
| **7** | Done | NDE↔GXA bridge: identifier in NDE queries + GXA/GEO links in table |
| **8** | Done | Limitations & guardrails documented in README and context pack |
| **9** | Future | Meta-coverage / observatory queries (after UI update, e.g. expose template) |
| **10** | Future | Diagrams (after UI update) |

### Phase 5 – done

**Phase 5 (NL routing):**
- [x] Run `./scripts/test_gxa_phase5.sh` end-to-end; review complete, no further comments
- [ ] Optional: confirm Phase 4 filters (organism, tissue, factor, disease) from chat when `allow_open_nl2sparql` is on
- [ ] Optional: spot-check all 6 GXA tasks from the chat UI with representative questions

**Phase 5a (metadata links):**
- [x] Experiment ID links (GXA, GEO, AE) – done
- [x] Gene URI links – done
- [ ] Optional: chained API for richer sample metadata (defer if not blocking)


### Phase 5 manual spot-checks (chat UI)

Run the web-v2 dev server (`cd web-v2 && npm run dev`) and test these questions in the chat UI at http://localhost:3000:

| Question | Expected task | What to verify |
|----------|----------------|----------------|
| Which genes are differentially expressed in E-GEOD-76? | gene_expression_genes_in_experiment | Results table with experimentId, contrastLabel, geneSymbol, log2fc; GXA/GEO links on experiment IDs |
| Where is DUSP2 upregulated? | gene_expression_experiments_for_gene | Results with experiment IDs, contrast labels, log2fc; gene links |
| Summarize DUSP2 differential expression across experiments | gene_expression_gene_cross_dataset_summary | Rows per (experiment, contrast) with direction, log2fc |
| Find genes upregulated in multiple experiments | gene_expression_genes_agreement | geneSymbol, direction, experimentCount |
| Find genes differentially expressed in opposite directions | gene_expression_genes_discordance | geneSymbol, experimentIdUp, experimentIdDown, contrast labels |
| What gene expression datasets exist? | gene_expression_dataset_search | experimentId, contrastCount, sampleContrastLabel |
| Gene expression datasets in mouse | gene_expression_dataset_search | Same shape; results filtered to mouse (organism_taxon_ids) |
| What gene expression datasets exist for heart disease? | gene_expression_dataset_search | Same shape; results filtered to heart disease (disease_efo_ids) |
| Find datasets about influenza that contain gene expression data | dataset_search | NDE results (name, description, identifier); GXA columns for rows with GSE; NDE direct endpoint used |

**Phase 4 filter extraction:** Questions 7–8 require LLM slot-filler (`allow_open_nl2sparql`). If LLM is not configured, these may fall back to unfiltered results. Check the Inspect panel to see if `slots` include `organism_taxon_ids` or `disease_efo_ids`.

**Backend support for "datasets about X" and "gene expression about X":**
- **NDE path (working in web app):** "Find datasets about influenza that contain gene expression data" is routed to **dataset_search**. When keyword fallback terms are present, the template uses the **simple keyword-only query** (`buildNDEFallbackQuery`) so the NDE endpoint returns results. **Execute routing:** The SPARQL execute route decides GXA vs NDE direct by **query content** (whether the query contains `gene-expression-atlas-okn`), not by `intent.graphs`, so NDE queries still go to the NDE endpoint when the user says "contain gene expression data". NDE results show GXA/GEO links when `identifier` is a GSE ID; the two-phase bridge adds experimentId, contrastCount, sampleContrastLabel for rows with GSE when `include_gxa_bridge` is set.
- **NDE execution:** NDE-only queries go to the **NDE direct endpoint**; `FROM` clauses are stripped (default graph has the data). Routing uses query content (query contains "nde", query does not contain "gene-expression-atlas-okn").
- **Active NDE↔GXA bridge:** Slot-filler sets `include_gxa_bridge: true` for "contain gene expression data" / "with gene expression". Executor runs two-phase: NDE query then GXA coverage for each GSE; merges experimentId, contrastCount, sampleContrastLabel. GEO not in FRINK; only links from GSE identifiers.
- **GXA path:** "Find gene expression experiments about influenza" (or "gene expression datasets about influenza") stays **gene_expression_dataset_search**. The heuristic slot filler extracts the phrase after "about" / "related to" / "for" into **factor_terms** (and **disease_efo_ids** when a known disease mapping exists, e.g. influenza → EFO 0001072). When **both** factor_terms and disease_efo_ids are present, the GXA coverage query uses **OR logic (UNION)**: experiments that match factor (e.g. "influenza" in contrast label) **or** disease (Study--studies-->EFO) are returned, so we don’t over-constrain. If you still get 0 results, the graph may have no influenza-related experiments in either branch.

### Phase 8 – Limitations & guardrails (done)

- **README** (project root): New section "Chat UI and query service (web-v2)" documents endpoints (FRINK, NDE and GXA direct), timeouts (25s default, 120s for GXA), result limits (max_limit 500, max_rows_download 2000), forbidden SPARQL operations, and that GEO is not in FRINK (links only). Notes that template exposure and Phases 9–10 are planned for after a future UI update.
- **Context pack** (`web-v2/context/packs/wobd.yaml`): Comment block above `guardrails` explains max_limit, timeout_seconds, max_rows_download, forbid_ops, and that GEO is not a graph in FRINK.

### Future work (Phases 9–10, after UI update)

- **Phase 9 (Meta-coverage / observatory):** Queries or UI that show what graphs and templates are available, coverage stats, etc. Deferred until after the UI is updated (e.g. to expose the query template to the user).
- **Phase 10 (Diagrams):** Structured SPARQL output driving a frontend charting library. Deferred until after the UI update.

### Phase 6 – Evidence-centric UI (updated scope)

A **new UI workflow** is planned after gene expression work is finished. Phase 6 does not build a full evidence UI in the current chat; it **captures requirements** for the new workflow and does **minimal current-UI improvements** so results are interpretable now.

**Part A – Requirements for the new UI**

- Document that GXA result rows must expose:
  - **Contrast label** – which comparison produced the result (e.g. “treatment vs control”, “tissue A vs tissue B”).
  - **Evidence / provenance** – a way for users to see “why am I seeing this?” (experiment → contrast → association → gene; contrast definition and factors).
- Store in this doc or a short “GXA UI requirements” note so the new workflow design can adopt these.

**Part B – Minimal current-UI improvements**

- Ensure **contrast label is always present and readable** in the current results table for all GXA tasks that return per-contrast rows (e.g. genes in experiment, experiments for gene, cross-dataset summary, discordance). No new evidence panel or tooltips in the current UI; only what’s needed for correctness and basic interpretability.

**Phase 6 checklist**

- [x] Add or update a "GXA evidence UI requirements" section (contrast label + evidence/provenance) for the new workflow.
- [x] Verify current results table shows contrast label for every GXA task that has per-contrast results; fix any missing or unreadable contrast columns.

#### GXA evidence UI requirements (for new workflow)

Requirements for the **new UI workflow** (to be implemented after gene expression work). GXA result rows must expose:

1. **Contrast label** – Which comparison produced the result (e.g. "treatment vs control", "tissue A vs tissue B"). Every row tied to a specific contrast must show the contrast label so users see *what* the differential expression is relative to, not just the gene and experiment ID.
2. **Evidence / provenance** – A way for users to answer "why am I seeing this?":
   - **Evidence path:** experiment → contrast → association → gene (what was compared, and how the row was derived).
   - **Contrast definition:** factors (e.g. factor 1 vs factor 2), optional tissue/organism context.
   - **Provenance:** source experiment, contrast ID, and link to GXA/GEO where applicable.

The new workflow should adopt these so GXA results remain interpretable and trustworthy. The current chat UI satisfies (1) via contrast label columns and (2) only in part (links to GXA/GEO; full evidence panel deferred to the new UI).

### Phase 10 – Diagrams (moved to end)

Diagrams are **Phase 10** (end of plan). Rationale: they depend on stable queries, are additive UI polish, and evidence UI (Phase 6) and guardrails (Phase 8) are higher priority for correctness and trust.

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

### 5. Suggested web app test questions

These questions can be tried in the chat UI (`http://localhost:3000`). The classifier routes to `gene_expression_dataset_search` when text contains ("gene expression" OR "expression dataset" OR "differential expression" OR "expression experiment") AND ("dataset" OR "list" OR "what" OR "which").

| Question | Expected task | Notes |
|----------|---------------|-------|
| What gene expression datasets exist? | gene_expression_dataset_search | Basic coverage, no filters |
| List gene expression experiments | gene_expression_dataset_search | Same as above |
| Which gene expression experiments have differential expression? | gene_expression_dataset_search | Same as above |
| What gene expression datasets exist? Limit 20 | gene_expression_dataset_search | Limit extracted heuristically |

**Phase 5 (in progress):** Classifier now routes to all GXA tasks. Heuristic slot-filler extracts experiment_id, gene_symbols, gene_symbol, direction. LLM slot-filler (when allow_open_nl2sparql) extracts Phase 4 filters (organism_taxon_ids, tissue_uberon_ids, factor_terms, disease_efo_ids) for GXA tasks. Test with `./scripts/test_gxa_phase5.sh`.

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

---

## Phase 4 – contextual queries (ontology-grounded filters)

Phase 4 adds optional context filters to all GXA templates:

- **`organism_taxon_ids`** – NCBITaxon IDs (e.g. `10090` Mus musculus, `9606` Homo sapiens)
- **`tissue_uberon_ids`** – UBERON IDs (e.g. `0002082` heart, or `UBERON_0002082`)
- **`factor_terms`** – Plain-text substring match (CONTAINS) on contrast labels and `factors_1`/`factors_2` strings. **Not ontology-grounded** – does not use EFO, XCO, or other ontologies. Terms like `aortic banding` or `surgery` are matched as literal substrings in the stored labels.
- **`disease_efo_ids`** – EFO Disease IDs (e.g. `0001461`, `0002460`, or `EFO_0001461`). Ontology-grounded: filters by Study → `studies` → Disease (EFO individuals). Only in `gene_expression_dataset_search` for now.

Slot aliases: `species` → `organism_taxon_ids`, `tissue_iris` → `tissue_uberon_ids`, `perturbation` → `factor_terms`, `disease_iris` → `disease_efo_ids`.

**Note on factor_terms:** "aortic banding" appears in local E-GEOD-76 data but may not be present in the FRINK endpoint’s coverage. The XCO term [XCO:0001462](https://www.ebi.ac.uk/ols4/ontologies/xco/classes/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FXCO_0001462) (transverse aortic banding) is not used by the current implementation; ontology-grounded factor filtering could be a future enhancement.

### 1. Dataset search with filters

```bash
curl -s -X POST http://localhost:3000/api/tools/nl/intent-to-sparql \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_dataset_search",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {
        "organism_taxon_ids": "10090",
        "tissue_uberon_ids": "0002082",
        "factor_terms": "aortic banding",
        "disease_efo_ids": "0001461",
        "limit": 20
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

Disease filter (`disease_efo_ids`): EFO IDs like `0001461` (heart disease) or `0002460` (hypertension). Filters experiments whose Study has `studies` linking to the given EFO Disease individuals.

### 2. Genes in experiment with organism filter

Use an experiment whose genes have the given organism. E-GEOD-76 is mouse (10090); E-GEOD-23301 is Arabidopsis (3702).

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
        "experiment_id": "E-GEOD-76",
        "organism_taxon_ids": "10090",
        "limit": 20
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

### 3. Experiments for gene with factor filter

Use a factor term that appears in FRINK contrast labels (e.g. `surgery`, `sham`). "aortic banding" is in local E-GEOD-76 but FRINK coverage may differ.

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
        "factor_terms": "surgery",
        "limit": 20
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

### 4. Cross-dataset summary with organism filter

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
      "slots": {
        "gene_symbol": "DUSP2",
        "organism_taxon_ids": "10090",
        "limit": 20
      }
    },
    "pack_id": "wobd"
  }' | jq -r '.query'
```

### 5. Agreement / discordance with filters

Same pattern: add `organism_taxon_ids`, `tissue_uberon_ids`, or `factor_terms` to `slots` when calling intent-to-sparql. Execute via `/api/tools/sparql/execute` with `mode: "federated"` and `graphs: ["gene-expression-atlas-okn"]`.

**Quick test:** `./scripts/test_gxa_phase4.sh` (requires dev server running).

### Introspection and YAML metadata

The GXA graph uses **biolink:Study** (`https://w3id.org/biolink/vocab/Study`) as its primary entity, not `schema:Dataset`. The introspection script `scripts/build_graph_context.py` reads `primary_class` from `web-v2/context/graphs/gene-expression-atlas-okn.yaml` when building context, so dataset_properties are correctly derived from Study individuals (e.g. `studies` → Disease EFO). Rebuild context with:

```bash
python scripts/build_graph_context.py build-one --graph gene-expression-atlas-okn --endpoint https://frink.apps.renci.org/gene-expression-atlas-okn/sparql --type knowledge_graph
```

### Phase 4 known limitations

- **factor_terms** uses plain text CONTAINS on contrast labels and factor strings – it does **not** use EFO, XCO, or other ontologies. Terms like "aortic banding" or "transverse aortic banding" are matched as literal substrings only. Ontology-grounded factor filtering (e.g. XCO:0001462) could be a future enhancement.
- **FRINK vs local data**: The FRINK `gene-expression-atlas-okn` endpoint may have different experiment coverage than local TTL files. "aortic banding" appears in local E-GEOD-76; FRINK may or may not include that experiment.
- **Factor filter optimization**: Factor filter queries now use a subquery that selects matching contrasts *before* joining to associations, which can avoid timeout by reducing the solution space. If factor filter still times out, try organism/tissue filters instead.

---

## Phase 5 – NL routing & slot filling for GXA (In progress)

Make all GXA tasks and Phase 4 filters reachable from the chat UI via natural language.

### Scope

1. **Classifier updates** – Route NL questions to all GXA tasks:
   - `gene_expression_genes_in_experiment` – e.g. "Which genes are DE in E-GEOD-76?"
   - `gene_expression_experiments_for_gene` – e.g. "Which experiments show DE of DUSP2?"
   - `gene_expression_gene_cross_dataset_summary` – e.g. "Summarize DUSP2 DE across experiments"
   - `gene_expression_genes_agreement` – e.g. "Genes upregulated in multiple experiments"
   - `gene_expression_genes_discordance` – e.g. "Genes DE in opposite directions across contrasts"

2. **Slot filling for GXA** – Extract from natural language:
   - `experiment_id` – experiment accessions (e.g. E-GEOD-76)
   - `gene_symbols` / `gene_symbol` – gene symbols (e.g. DUSP2)
   - Phase 4 filters: `organism_taxon_ids`, `tissue_uberon_ids`, `factor_terms`, `disease_efo_ids`
   - Optional: `direction` (up/down), `min_experiments`, `limit`

### Implementation approach

- **Classifier** (`web-v2/lib/intent/classifier.ts`): Add pattern rules or LLM-based classification for GXA tasks. Consider entity detection (gene symbols, experiment IDs) to disambiguate.
- **Slot filler** (`web-v2/lib/intent/slot-filler.ts`): Add heuristic extraction for experiment IDs (E-GEOD-*), gene symbols (capitalized short names), and limit.
- **LLM slot filler** (`web-v2/lib/intent/slot-filler-llm.ts`): Extend to GXA tasks (currently only runs for `dataset_search`). Add schema for GXA slots including Phase 4 filters. Consider ontology-grounded extraction (e.g. "mouse" → NCBITaxon:10090, "heart" → UBERON:0002082) via entity identification.

### Target test questions (chat UI)

| Question | Expected task |
|----------|---------------|
| Which genes are differentially expressed in E-GEOD-76? | gene_expression_genes_in_experiment |
| Where is DUSP2 upregulated? | gene_expression_experiments_for_gene |
| Summarize DUSP2 differential expression across experiments | gene_expression_gene_cross_dataset_summary |
| Find genes upregulated in multiple experiments | gene_expression_genes_agreement |
| Find genes differentially expressed in opposite directions | gene_expression_genes_discordance |
| Gene expression datasets in mouse | gene_expression_dataset_search (with organism_taxon_ids) |
| Heart disease gene expression experiments | gene_expression_dataset_search (with disease_efo_ids) |

### Phase 5 test script

```bash
bash scripts/test_gxa_phase5.sh
```

Requires dev server running (`cd web-v2 && npm run dev`). Tests NL flow: question → intent (classifier + slot filler) → SPARQL → execute.

### Query behavior notes

- **Genes agreement** – Looks across **multiple experiments** (not contrasts within one experiment). Groups by gene and direction (up/down), counts `COUNT(DISTINCT ?experimentId)`, returns `sampleExperimentId` as one example. A gene must be DE in the same direction in ≥ `min_experiments` distinct experiments.
- **Genes discordance** – Returns genes DE up in some contrasts and down in others. Response includes `experimentIdUp`, `experimentIdDown`, `contrastLabelUp`, `contrastLabelDown` so you can see which experiment/contrast shows up vs down.
- **Gene cross-dataset summary** – One row per (gene, experiment, contrast) with direction, log2fc, adj_p_value. Requires `gene_symbol` (or `gene_symbols[0]`).

---

## Phase 5a – GEO/GXA sample metadata (In progress)

Provide richer sample metadata (tissue, disease, treatment, etc.) in query results beyond array design/measurement.

### Implemented: Links to GXA/GEO/ArrayExpress and gene/contrast URIs

The ResultsTable (`web-v2/components/chat/ResultsTable.tsx`) now renders:

1. **Experiment ID columns** (`experimentId`, `sampleExperimentId`, `experimentIdUp`, `experimentIdDown`) with clickable links:
   - **E-GEOD-*** → GXA (Expression Atlas) and GEO (NCBI)
   - **E-MTAB-*** → GXA and ArrayExpress
   - Links appear as styled badges ("GXA ↗", "GEO ↗", "AE ↗") next to the experiment ID.

2. **Gene column** – Gene URIs are rendered as clickable links (Ensembl, NCBI Gene, etc.). Contrast URLs are not linked (they don't resolve to public pages).

Value extraction uses `extractCellValue()` to handle both raw strings and SPARQL `{type, value}` binding objects.

**How to test:** Run a GXA query (e.g. "Which genes are DE in E-GEOD-76?") and click a result message to open the Inspect panel. In the Results table, experiment ID cells show GXA/GEO links; gene cells show clickable links.

### WOBD vs Expression Atlas data

WOBD queries the `gene-expression-atlas-okn` graph (SPOKE/Genelab via FRINK), while the [Expression Atlas](https://www.ebi.ac.uk/gxa/experiments/E-GEOD-76/Results) website uses EMBL-EBI's live data. The OKN graph can differ from live GXA (different pipelines, versions, or contrast coverage), so results may not match 1:1.

Optional slots `min_abs_log2fc` and `max_adj_p_value` let you apply GXA-style cutoffs (e.g. `min_abs_log2fc: 1`, `max_adj_p_value: 0.05`) when you want to align with Expression Atlas filters. By default, no cutoffs are applied so WOBD shows all DE genes in the OKN graph.

### Local verification (query vs local RDF)

The SPARQL query has been verified against local GXA TTL data in `data/gene_expression/`:

```bash
python scripts/verify_gxa_query_local.py --list-contrasts          # List contrasts and gene counts
python scripts/verify_gxa_query_local.py --contrast "1 hour"       # DE genes for aortic banding 1h vs sham 1h
python scripts/verify_gxa_query_local.py --contrast "1 hour" --min-abs-log2fc 0.6 --max-adj-p-value 0.05
```

**Findings for E-GEOD-76, contrast "aortic banding at 1 hour vs sham at 1 hour" (g7_g1):**

| Source | Genes returned |
|--------|----------------|
| **Raw data (before loading)** | 3 genes: **Atf3** (1.1, adjP≈0.007), **Dynll2** (−1.0, adjP≈0.009), **Ccl2** (1.3, adjP≈0.048) |
| GXA website (foldChange 1, pValue 0.05) | Same 3 genes as raw data (Atf3, Dynll2, Ccl2) |
| Local `E-GEOD-76.ttl` | 3 genes: **1500011B03Rik** (−0.8), **Atf3** (1.1), **Mark2** (0.7) |
| FRINK / WOBD | 3 genes (same as local) |
| Graph with foldChange 1, pValue 0.05 | 1 gene: Atf3 (log2fc=1.1) |

**Critical finding:** The raw analytics data (before loading into the graph) shows **Atf3, Dynll2, Ccl2** for g7_g1 with foldChange 1 and pValue 0.05—matching the GXA website. The graph has **1500011B03Rik, Atf3, Mark2** for g7_g1—different genes. Dynll2 and Ccl2 appear in the graph but are associated with **g12_g6** (48 hour), not g7_g1. See [E-GEOD-76 Results](https://www.ebi.ac.uk/gxa/experiments/E-GEOD-76/Results?specific=true&geneQuery=%255B%255D&filterFactors=%257B%2522TIME%2522%253A%255B%25221%2520hour%2522%255D%257D&cutoff=%257B%2522foldChange%2522%253A1%252C%2522pValue%2522%253A0.05%257D&regulation=%2522UP_DOWN%2522).

**Conclusion:** The SPARQL query is correct. The **graph builder** that produced the TTL file has a **contrast mapping or column assignment error**—genes from one contrast (e.g. g12_g6) may have been incorrectly assigned to g7_g1, or the wrong column was read when parsing the analytics TSV. The raw data and GXA agree; the graph does not.

**Likely causes of graph vs raw/GXA mismatch:**

1. **Contrast column mix-up** – When parsing the analytics TSV (one row per gene, multiple contrast columns), the wrong column pair (adj_p_value, log2fc) may have been used for g7_g1.
2. **Contrast ID mapping** – Group IDs (g7, g1) in the graph may not align with the column order in the source TSV.
3. **Different data version** – Graph from an older analytics file; raw data is from current GXA.


**How to compare manually:**

1. Export our graph’s gene list:
   ```bash
   python scripts/verify_gxa_query_local.py --contrast "1 hour" --min-abs-log2fc 1 --max-adj-p-value 0.05 --export-csv graph_genes.csv
   ```
2. Download GXA analytics from [E-GEOD-76 Downloads](https://www.ebi.ac.uk/gxa/experiments/E-GEOD-76/Downloads) (analytics TSV).
3. Filter GXA TSV to the same contrast (aortic banding 1h vs sham 1h) and apply |log2fc| ≥ 1, adj p ≤ 0.05.
4. Diff the gene lists to see which genes appear in only one source.

**Files:**
- `scripts/verify_gxa_query_local.py` – Run GXA queries against local TTL files; `--export-csv` for comparison
- `queries/gxa_egeod76_1hour.sparql` – Query for aortic banding 1h vs sham 1h contrast

### Future options

- **Chained API calls** – Call GEO API or GXA API to fetch metadata and display inline.
- **Extend SPARQL** – If the KG contains sample-level metadata, extend queries to include it.

**Scope:** Decide whether enrichment is per-experiment, per-contrast, or per-sample.

---

## Phase 10 – Diagrams (Pending)

Generate visualizations (bar charts, heatmaps, volcano plots) from structured SPARQL output.

**Approach:**
- SPARQL templates already return structured data (log2fc, direction, contrastLabel, etc.).
- Add frontend charting library (e.g. Chart.js, D3.js, Recharts) to render diagrams from this data.

---

## Phase 7 – NDE↔GXA bridge (Done)

Connect NDE datasets to GXA expression data so users can discover expression evidence for NDE datasets.

**Context:**
- NDE datasets have `schema:identifier` (GSE IDs for NCBI GEO datasets).
- GXA uses E-GEOD accessions (e.g. `E-GEOD-76`).
- GSE and E-GEOD align (e.g. GSE76 ↔ E-GEOD-76) for GEO datasets mirrored in ArrayExpress.

**Scope:**
- Include `schema:identifier` in NDE dataset search SELECT so GSE IDs appear in results.
- In results table: when a row has a GSE ID (e.g. GSE76), show a link "Expression data (GXA)" that opens the corresponding E-GEOD experiment in Expression Atlas (E-GEOD-{n}).
- Optional later: template "expression data for NDE dataset X" (resolve NDE → GSE → E-GEOD → `gene_expression_genes_in_experiment`); NL routing when viewing an NDE result.

**Phase 7 checklist:**
- [x] Add `?identifier` to NDE dataset query SELECT (OPTIONAL schema:identifier).
- [x] In ResultsTable, for NDE results with identifier matching GSE\d+, show link to GXA (E-GEOD-{n}) and GEO.

### Phase 9 – Meta-coverage / observatory (moved)

Meta-coverage and observatory queries are **Phase 9** (after NDE↔GXA bridge and guardrails). See top table.
