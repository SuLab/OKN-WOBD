# WOBD Web v2

**Template-based SPARQL discovery** for the Web of Biological Data: a Next.js application that runs curated query templates against the [FRINK](https://apps.okn.us/) **federation** SPARQL endpoint (graph scope via `FROM` / intent `graphs`; see **Endpoint routing** below), with a provider-neutral **Tool Service API** under `app/api/tools/`.

Natural language is still used where it helps (for example, optional LLM-assisted routing on the legacy chat page), but the **supported product surface** is the home page plus `/template/{templateId}` slot forms that generate vetted SPARQL. The **landing cards** are defined in `lib/landing/template-meta.ts` (currently **Datasets by keywords**, **Gene-level differential expression per contrast**, and **Datasets for a drug**); other templates in `context/packs/wobd.yaml` are reachable only via direct `/template/<id>` URLs unless you add them to that list.

---

## Legacy interfaces (not maintained)

| Interface | Location | Notes |
|-----------|----------|--------|
| **Streamlit NL→SPARQL app** | [`web/`](../web/README.md) at the repo root | Older Python/Streamlit UI; dependencies and deployment docs in that folder are historical. |
| **Conversational chat UI** | `http://localhost:3000/chat` (route `app/chat/`) | Multi-turn chat, Lane B (LLM SPARQL), Lane C (raw SPARQL), `@graph` / `@suggest` / `@diagram` commands, and multi-hop planning. **Not maintained** for new features or parity with the template UI; bugs are best-effort only. |

---

## Template-based query application (maintained)

### User flow

1. **Landing (`/`)** — Describes WOBD and lists **query cards** for the primary templates (see `lib/landing/template-meta.ts`). Each card links to a dedicated template page.
2. **Template page (`/template/{templateId}`)** — Loads the WOBD context pack, renders a **slot form** (`SlotForm`) for that template’s required and optional fields (keywords, ontology-backed disease/species pickers, GXA filters, drug names, and so on), then runs the query.
3. **Results** — Tabular results (`ResultsTable`), optional **NDE card** layout for dataset-shaped bindings, **MONDO descendant expansion** recap when used, downloadable CSV/TSV within pack limits, and **“Show queries”** for the exact SPARQL (or multi-step queries for `drug_datasets`).
4. **Expert inspection** — On-template **Monaco SPARQL editor** (`SparqlEditor`) lets you review the generated SPARQL where enabled.

Templates declared in [`context/packs/wobd.yaml`](./context/packs/wobd.yaml) are the source of truth for **template IDs**, slot names, and descriptions. Cards on `/` are a **subset**; additional templates (for example `geo_dataset_search`, `gene_expression_dataset_search`) are reachable at `/template/<id>` even when they do not appear on the landing grid. As the project developed, only a subset of query cards were displayed on the Home page, however code for all developed query cards was kept in the project.

### Home-page templates and autocomplete (sources)

The three landing cards (`lib/landing/template-meta.ts`) use `SlotForm` suggestions from `/api/tools/ontology/...` and Wikidata:

| Card | `template` id | Autocomplete backing |
|------|----------------|----------------------|
| Datasets by keywords | `dataset_search` | **MONDO** → OLS (`mondo/search`, `lib/ontology/mondo-ols.ts`). **NCBITaxon** (host / pathogen) → OLS (`ncbitaxon/search`, `ncbitaxon-ols.ts`). Optional **MONDO subclass expansion** → OLS4 v2 entities (`mondo-descendants-ols.ts`). |
| Gene-level differential expression per contrast | `gene_expression_gene_level_de_per_contrast` | **Genes** → HGNC REST (`hgnc/search`, `hgnc-client.ts`). **Taxon** → OLS (`ncbitaxon/search`). **Tissue** → OLS UBERON (`uberon/search?source=ols`). **EFO** (factors, disease) → OLS (`efo/search`, `efo-ols.ts`). |
| Datasets for a drug | `drug_datasets` | **Drugs** → Wikidata (`wikidata/drugs`, `wikidata-client.ts`). |

### How SPARQL is produced and executed

Template **Run** reuses **`POST /api/tools/nl/intent-to-sparql`** because that API was built for the chat app’s **Lane A** path (intent JSON → template SPARQL). The template UI fills **`Intent`** from the form (`lib/dashboard/run-query.ts` → **`buildIntent`**) instead of using **`nl/intent`**, but still calls **`intent-to-sparql`** so generation stays centralized in **`generateSPARQLFromIntent`** (`lib/templates/generator.ts`, `lib/templates/templates/`)—except **`drug_datasets`**, which uses **`POST /api/tools/drug-datasets`** only (multi-step: drug resolution, Wikidata, NDE search; the UI can show each executed query). On the **home page**, **`dataset_search`** and **`gene_expression_gene_level_de_per_contrast`** go through **`intent-to-sparql`**; **`drug_datasets`** does not.

**Endpoint routing (home-page templates):** `POST /api/tools/sparql/execute` always posts to the FRINK **federated** SPARQL URL from the context pack (never the standalone NDE or GXA SPARQL HTTP URLs). **`dataset_search`** uses `graphs: ["nde"]`. **`gene_expression_gene_level_de_per_contrast`** uses `graphs: ["gene-expression-atlas-okn"]`. **`drug_datasets`** is orchestrated by `POST /api/tools/drug-datasets` with federated steps over **Wikidata** and **NDE** (`lib/dashboard/drug-datasets-plan.ts`). Other `/template/...` IDs may use different `graphs` (see `lib/dashboard/run-query.ts` → `buildIntent` and the pack file). GXA-related tasks still set the GXA graph in intent so timeouts behave correctly (see `app/api/tools/sparql/execute/route.ts` and `docs/gene_expression_query_progress.md` in the repo root).

### Template catalog (WOBD pack)

Declared under `templates:` in `context/packs/wobd.yaml` (ids and slots may evolve in that file). **\*** next to a template id means it has a **query card on the home page** (`/`); the list is defined in **`lib/landing/template-meta.ts`** (currently three cards).

| Template id | Purpose (summary) |
|-------------|-------------------|
| `dataset_search` * | NDE datasets by keywords and/or disease, species, pathogen filters; optional GEO/E-GEOD hint filter. |
| `geo_dataset_search` | GEO series (GSE) in NDE with optional filters. |
| `drug_datasets` * | NDE datasets for diseases treated by a drug; optional “gene expression only” filter; multi-step API. |
| `entity_lookup` | Resolve a CURIE, URI, or label via configured graphs. |
| `gene_expression_dataset_search` | List GXA experiments with DE results. |
| `gene_expression_genes_in_experiment` | DE genes for an experiment/contrast. |
| `gene_expression_experiments_for_gene` | Experiments where a gene is DE. |
| `gene_expression_gene_cross_dataset_summary` | Cross-experiment summary for one gene. |
| `gene_expression_gene_level_de_per_contrast` * | Gene-level DE metrics per contrast. |
| `gene_expression_genes_agreement` | Genes DE in the same direction across experiments. |
| `gene_expression_genes_discordance` | Genes DE in opposite directions across contrasts. |

User-facing titles and blurbs for home-page cards and template headers are curated in **`lib/landing/template-meta.ts`**.

### Guardrails (execution)

Configured on the pack (`guardrails` in `wobd.yaml`): max `LIMIT`, request timeouts (GXA-shaped queries use a longer timeout on the **federated** execute call), max download rows, allowed `SERVICE` policy, and forbidden update operations. All execution goes through **`POST /api/tools/sparql/validate`** and **`POST /api/tools/sparql/execute`** unless handled inside `drug-datasets`.

---

## Query lanes (architecture)

The codebase still implements three lanes for SPARQL generation:

| Lane | Name | Role |
|------|------|------|
| **A** | Template-based (default) | Structured intent → vetted templates → SPARQL. **Primary path for `/template/...`.** |
| **B** | LLM-generated SPARQL | Open NL → SPARQL with schema hints; higher cost/variance. Used from **legacy `/chat`** (`/text`, `/open`). |
| **C** | User SPARQL | Raw editor; **legacy `/chat`** (`/sparql`). |

The **Tool Service API** enforces the same guardrails regardless of lane.

---

## Quick start

### Prerequisites

- Node.js 18+ and npm
- Network access to FRINK (defaults in `context/packs/wobd.yaml`)

### Installation

```bash
cd web-v2
npm install
```

### Configuration

1. **Create `.env.local`** (helper script):

   ```bash
   ./setup-env.sh
   ```

2. **Edit `.env.local`** — The **supported template app** (three home-page flows + ontology autocomplete) does **not** require any LLM API keys. Set **`ANTHROPIC_SHARED_API_KEY`** (and optionally **`OPENAI_SHARED_API_KEY`**, budget caps) only if you still use **legacy `/chat`** or other server-side LLM routes.

### Run

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) for the template landing page. Restart the dev server after changing env vars.

---

## Project structure

**Legend**

| Tag | Meaning |
|-----|---------|
| **[T]** | Primary **template UI** path: home page (`/`), `/template/...`, and the Tool Service routes those pages call. |
| **[S]** | **Shared** infrastructure (global layout, SPARQL execution, LLM proxy, types, etc.); also used by legacy `/chat` where noted. |
| **[C]** | **Legacy conversational** `/chat` only; not part of the maintained template product. |

**Template UI (what we maintain)** **[T]**

```
web-v2/
├── app/
│   ├── page.tsx                 # Landing (query cards)
│   ├── about/                   # About page
│   ├── template/[templateId]/   # Slot forms + results for each template
│   └── api/tools/               # Tool Service: SPARQL, context packs, registry, drug-datasets, ontology search, …
├── components/
│   ├── dashboard/               # SlotForm, NDE cards, MONDO expansion recap
│   └── landing/                 # QueryCards, landing copy
├── context/
│   ├── packs/                   # Context pack YAML (e.g. wobd.yaml)
│   └── graphs/                  # Graph metadata (*_global.json, YAML); see repo root scripts
├── lib/
│   ├── dashboard/               # runTemplateQuery, drug-datasets-plan, NDE↔GXA helpers
│   ├── landing/                 # template-meta.ts (home-page cards)
│   ├── templates/               # registry, generator, lib/templates/templates/*
│   ├── context-packs/           # Pack loader / types (used by Tool Service)
│   ├── ontology/                # OLS + Wikidata clients for slot autocomplete; GXA/NDE SPARQL helpers
│   └── registry/                # Graph list / suggestions backing registry API routes
└── docs/
    └── DEPLOYMENT.md            [T] Deploying this **template-based** Next.js app (EC2, systemd, Docker)
```

**Also in the repo** **[S]** / **[C]**

```
web-v2/
├── app/
│   ├── chat/                    [C] Legacy conversational UI (`/chat`)
│   └── api/context-packs/       [C] Pack listing used by `/chat` (templates use `api/tools/context/packs/…` instead)
├── components/
│   ├── layout/                  [S] Header, Footer (all routes)
│   └── chat/                    [S] ResultsTable, SparqlEditor reused on template pages; other files are `/chat`-only
├── lib/
│   ├── sparql/                  [S] Validation, execution, repair (all SPARQL runs)
│   ├── llm/                     [S] LLM proxy + providers (e.g. `/chat` Lane B; optional server-side use)
│   ├── keys/                    [S] BYOK session key handling
│   ├── runs/                    [S] Run record types / store for execute metadata
│   ├── graph-context/           [S] Graph context adapters for tooling
│   ├── agents/                  [S] `query-executor` runs `drug_datasets` steps; planner / visualization mostly for `/chat`
│   ├── chat/                    [C] Client-side `/chat` executor, messages, session, download helpers
│   └── intent/                  [C] NL routing + slot fill for `nl/intent` (conversational Lane A from free text)
├── types/                       [S] Shared TypeScript types (intents, results, …)
├── data/                        [S] e.g. registry snapshot files used by tools
└── docs/
    └── DEPLOYMENT.md            [S] Same file as in the **[T]** tree — deployment / ops for this Next app (not runtime code)
```

`docs/DEPLOYMENT.md` appears **under both trees** on purpose: it documents shipping the **template-based** app (**[T]**), and it is **shared documentation** rather than a code path (**[S]**).

Paths marked **[C]** are retained from the conversational app and are **not maintained** for parity with the template UI; they may still call the same **[S]** Tool Service endpoints as the template flow.

---

## Context packs

Versioned YAML bundles (`context/packs/*.yaml`) control:

- Default and selectable **graphs**
- **SPARQL endpoints** (federation URL used at runtime; per-graph direct URLs for catalog/docs)
- **Prefixes**, **template** metadata, **intent_routing** thresholds
- **Guardrails** and **SERVICE** policy

**Default pack:** `context/packs/wobd.yaml`.

Graph JSON under `context/graphs/` is mostly built by `scripts/build_graph_context.py` (see `scripts/README.md` in the repo). **`wikidata_global.json` is hand-maintained** (Wikidata SPARQL introspection is unreliable).

---

## Tool Service API (summary)

Base path: **`/api/tools/`** (same origin as the Next app in dev).

| Area | Methods | Purpose |
|------|-----------|---------|
| Registry / graphs | `GET .../registry/graphs`, `GET .../graphs/info`, `GET .../graphs/diagram`, `GET .../registry/graphs/suggestions`, `POST .../registry/graphs/refresh` | List graphs, details, Mermaid diagrams, NL suggestions |
| Context packs | `GET .../context/packs`, `GET .../context/packs/{packId}` | List/load packs |
| SPARQL | `POST .../sparql/validate`, `POST .../sparql/execute`, `POST .../sparql/modify`, `POST .../sparql/summarize` | Validate and run queries |
| NL / intent (legacy chat + tooling) | `POST .../nl/intent`, `POST .../nl/intent-to-sparql`, `POST .../nl/open-query` | Classify intent, **Lane A** SPARQL from intent JSON, **Lane B** open NL → SPARQL |
| Drug pipeline | `POST .../drug-datasets` | **`drug_datasets`** multi-step execution |
| Ontology helpers | `POST .../ontology/mondo/search`, `.../ncbitaxon/search`, `.../uberon/search`, `.../efo/search`, `.../hgnc/search`, `.../ontology/wikidata/drugs` | Slot autocomplete / resolution in template forms |
| LLM proxy | `POST .../llm/complete`, `POST .../llm/test-key` | Server-side completions (keys from env) |
| Runs | `GET .../runs`, `GET .../runs/{runId}` | Run records where enabled |

---

## LLM API key management

**Not required** for the supported **template-only** product (three home-page flows). Use this section only if you enable **legacy `/chat`**, Lane B open SPARQL, or other features that call **`POST /api/tools/llm/complete`**.

- **Shared keys (env):** `ANTHROPIC_SHARED_API_KEY` (default provider for those LLM routes), optional `OPENAI_SHARED_API_KEY`, optional monthly caps.
- **BYOK:** Session keys for OpenAI / Anthropic / Gemini in the browser; some server routes still prefer a shared key.

All proxied LLM calls use **`POST /api/tools/llm/complete`** so secrets are not exposed to the client.

---

## SPARQL safety

- **Forbidden:** INSERT, DELETE, LOAD, CLEAR, DROP, CREATE, MOVE, COPY, ADD
- **Allowed query types:** SELECT / ASK (as enforced by validator)
- **LIMIT** injection/capping per pack
- **SERVICE** policy per pack (`allow_any_frink`, `allowlist`, `forbid_all`, etc.)

---

## Deployment and environment

- **Deploy (template app):** [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) (EC2, systemd, Docker).

**Environment variables — template-based app (supported product)**

The three home-page templates (`dataset_search`, `gene_expression_gene_level_de_per_contrast`, `drug_datasets`) use **form-built `Intent` → `intent-to-sparql` or `drug-datasets`**, plus **OLS / HGNC / Wikidata** HTTP APIs for autocomplete. **No LLM API keys are required** for those runs.

| Variable | Used? | Description |
|----------|-------|-------------|
| `NEXT_PUBLIC_FRINK_FEDERATION_URL` | Optional | Override FRINK federation SPARQL URL (the WOBD context pack already supplies the default used by `sparql/execute`). |

**Not used for template-only usage** (set only if you use legacy `/chat`, Lane B, or other LLM-backed routes)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_SHARED_API_KEY` | Shared Anthropic key: **`/chat`**, **`nl/intent`**, **`nl/open-query`**, **`llm/complete`**, optional LLM slot fill — **not** read for home-page “Run” on the three supported templates. |
| `OPENAI_SHARED_API_KEY` | Optional second LLM provider (same class of routes as above). |
| `SHARED_BUDGET_USD` / `SHARED_BUDGET_STOP_USD` | Budget caps when shared LLM keys are in use. |
| `USE_JSON_CONTEXT_FOR_PLANNER` | **`lib/agents/query-planner`** (multi-hop / conversational planning); **not** used by the home-page template form pipeline. |

---

## Development and testing

**LLM / Lane B smoke script** (optional):

```bash
node test-llm-sparql-generation.js --with-llm
```

**curl examples** for intent and validation: see [TESTING_LLM_SPARQL_GENERATION.md](./TESTING_LLM_SPARQL_GENERATION.md).

---

## Conversational `/chat` reference (not maintained)

If you still open `/chat`, the composer supported:

- **`@graph` / `@graphs`** — List FRINK graphs
- **`@graph <shortname>`** — Graph detail
- **`@suggest` / `@suggest <shortname>`** — NL question suggestions
- **`@diagram <shortname>`** — Mermaid class diagram from pack metadata
- **`/text` or `/open`** — Lane B
- **`/sparql`** — Lane C

These are **not** updated with the template-first roadmap; prefer **`/template/...`** and the Tool Service API.

---

## License

Same as parent project.
