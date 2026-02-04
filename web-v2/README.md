# WOBD Web v2

Chat UI for WOBD with template-based, LLM-generated, and user-generated SPARQL querying. This is a Next.js application that provides a provider-neutral Tool Service API and a modern web interface for querying biomedical datasets.

## Architecture Overview

WOBD Web v2 implements a tiered querying system with three "lanes":

- **Lane A — Template-based SPARQL (default)**: LLM outputs intent JSON, app generates SPARQL from vetted templates
- **Lane B — LLM-generated SPARQL (fallback)**: LLM generates SPARQL directly from natural language, constrained by context pack schema hints
- **Lane C — User-generated SPARQL (expert)**: User directly writes/pastes SPARQL

All queries are executed through a Tool Service API that enforces safety guardrails, SERVICE policies, and budget limits.

### Query Types Explained

The system supports three types of SPARQL query generation:

1. **Template-based SPARQL (Lane A - Default)**: 
   - LLM outputs structured intent JSON
   - App generates SPARQL from vetted, tested templates
   - Most reliable, predictable, and cost-effective
   - Best for common query patterns

2. **LLM-generated SPARQL (Lane B - Fallback)**:
   - LLM generates SPARQL directly from natural language
   - More flexible for novel or complex queries
   - Constrained by context pack schema hints and guardrails
   - Requires LLM API calls (higher cost)

3. **User-generated SPARQL (Lane C - Expert)**:
   - User writes/pastes SPARQL directly
   - Full control for expert users
   - No LLM involved (no cost)
   - Requires SPARQL knowledge

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Access to FRINK federation endpoint (default: `https://frink.apps.renci.org/federation/sparql`)

### Installation

```bash
cd web-v2
npm install
```

### Configuration

1. **Create `.env.local` file** using the setup script:
   ```bash
   ./setup-env.sh
   ```

2. **Edit `.env.local`** and add your API keys:
   ```bash
   # Required: Anthropic API key (default LLM provider)
   ANTHROPIC_SHARED_API_KEY=sk-ant-your-actual-key-here
   
   # Optional: OpenAI API key (if you prefer OpenAI)
   OPENAI_SHARED_API_KEY=sk-your-actual-key-here
   
   # Budget limits (already set by setup script)
   SHARED_BUDGET_USD=5
   SHARED_BUDGET_STOP_USD=4.5
   ```

   **Get your API keys:**
   - **Anthropic**: https://console.anthropic.com/settings/keys (default, recommended)
   - **OpenAI**: https://platform.openai.com/api-keys (optional)

   **Note:** The app uses **Claude Sonnet 4.5** by default. Anthropic API keys are required for LLM features.

### Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

**Important:** After setting environment variables, restart the dev server for changes to take effect.

## Project Structure

```
web-v2/
├── app/                    # Next.js App Router
│   ├── api/tools/         # Tool Service API endpoints
│   ├── chat/              # Chat UI page
│   └── page.tsx           # Landing page
├── components/            # React components
│   ├── chat/              # Chat UI components
│   ├── landing/          # Landing page components
│   └── ui/                # shadcn/ui components (to be added)
├── lib/                   # Core libraries
│   ├── context-packs/    # Context pack loader/validator
│   ├── sparql/           # SPARQL validation/execution
│   ├── llm/              # LLM provider abstractions
│   ├── keys/             # BYOK key management
│   └── runs/             # Run record storage
├── context/packs/        # Context pack definitions (YAML)
├── context/graphs/       # Graph context (*_global.json); wikidata is hand-maintained
└── types/                # Shared TypeScript types
```

## Context Packs

Context packs are versioned configuration bundles that control:
- Which graphs to query
- Prefixes and template library
- Allowed SERVICE endpoints
- Guardrails (limits, timeouts, policies)

Default pack: `context/packs/wobd.yaml`

### Creating a Context Pack

Create a YAML file in `context/packs/`:

```yaml
id: mypack
label: "My Pack"
version: "0.1.0"
endpoint_mode:
  default: federated
  federated_endpoint: "https://frink.apps.renci.org/federation/sparql"
graphs:
  default_shortnames: ["nde", "ubergraph"]
  allow_user_select: true
prefixes:
  schema: "http://schema.org/"
guardrails:
  max_limit: 500
  timeout_seconds: 25
  service_policy: "allow_any_frink"
templates:
  - id: dataset_search
    required_slots: ["keywords"]
```

### Graph context files

Graph metadata is loaded from `context/graphs/*_global.json`. Most of these are produced by `scripts/build_graph_context.py` (see `scripts/README.md`). **`wikidata_global.json` is hand-maintained** because SPARQL introspection of the Wikidata graph often returns 503; it is curated from Wikidata’s property documentation and from the project’s usage in the ontology and query-planner code.

## Chat Commands

The chat interface supports special `@` commands for graph discovery and query suggestions:

### Graph Commands
- `@graph` or `@graphs` - List all available graphs in FRINK Federated SPARQL with descriptions
- `@graph <shortname>` - Get detailed information about a specific graph (e.g., `@graph nde`)
  - Shows graph IRI, endpoint, description, and usage instructions

### Query Suggestions
- `@suggest` or `@suggestions` - Get natural-language question suggestions for all graphs (quick mode)
- `@suggest <shortname>` - Get question suggestions for a specific graph (e.g., `@suggest nde`)
  - Returns only natural-language questions you can type directly into the chat (no SPARQL examples)
  - Based on graph content (quick mode: descriptions; full mode: discovered health conditions, species, etc.)

### Schema Diagram
- `@diagram <shortname>` - Show a Mermaid diagram of knowledge graph classes for a graph (e.g., `@diagram nde`, `@diagram ubergraph`)
  - Uses context pack graph metadata: classes are derived from `good_for` (e.g. Dataset) and `queryable_by` entity types (e.g. Disease, Species, Gene)

### Mode Switching
- `/text` or `/open` - Switch to LLM-generated SPARQL mode (Lane B - LLM generates SPARQL directly)
- `/sparql` - Switch to User-generated SPARQL editor mode (Lane C - write SPARQL directly)

## Tool Service API

The Tool Service API provides stable HTTP endpoints for all WOBD operations:

### Registry / Graph Discovery
- `GET /api/tools/registry/graphs` - List available graphs
- `GET /api/tools/graphs/info?shortname=<name>` - Get graph details
- `GET /api/tools/graphs/diagram?shortname=<name>&pack_id=wobd` - Get Mermaid diagram of graph classes (from context pack metadata)
- `GET /api/tools/registry/graphs/suggestions?graphs=<name>&quick=true` - Get query suggestions
- `POST /api/tools/registry/graphs/refresh` - Manually refresh graph list from OKN Registry

### Context Packs
- `GET /api/tools/context/packs` - List all packs
- `GET /api/tools/context/packs/{packId}` - Get pack by ID

### SPARQL
- `POST /api/tools/sparql/validate` - Validate SPARQL query
- `POST /api/tools/sparql/execute` - Execute SPARQL query

### Natural Language / LLM
- `POST /api/tools/nl/intent` - Classify intent and route to lane
- `POST /api/tools/nl/intent-to-sparql` - Generate SPARQL from intent (template-based, Lane A)
- `POST /api/tools/nl/open-query` - Generate SPARQL directly from natural language (LLM-generated, Lane B) (template-based, Lane A)
- `POST /api/tools/nl/open-query` - Generate SPARQL directly from natural language (LLM-generated, Lane B)

### LLM Proxy
- `POST /api/tools/llm/test-key` - Test API key
- `POST /api/tools/llm/complete` - Proxy LLM calls (server-side only)

### Run Records
- `GET /api/tools/runs/{runId}` - Get run record
- `GET /api/tools/runs` - List run records (with filters)

## LLM API Key Management

WOBD Web v2 supports two modes for providing API keys:

### 1. Shared Keys (Recommended for Testing)

Configure API keys via environment variables in `.env.local`:

- **Anthropic (Default)**: Set `ANTHROPIC_SHARED_API_KEY` - Required for LLM features
- **OpenAI (Optional)**: Set `OPENAI_SHARED_API_KEY` - Alternative provider

**Features:**
- Enforced $5/month budget cap (configurable via `SHARED_BUDGET_USD`)
- Budget tracked server-side across both providers
- Shared keys are required for server-side LLM calls (e.g., entity identification)

### 2. Bring Your Own Key (BYOK)

- Supports OpenAI, Anthropic, and Gemini
- Keys stored in session (not persisted to disk)
- No budget limits for BYOK usage
- Frontend automatically generates and manages session IDs in localStorage

**Note:** Some server-side LLM calls require a shared key. For full functionality, set `ANTHROPIC_SHARED_API_KEY` in `.env.local`.

All LLM calls are proxied through the backend (`/api/tools/llm/complete`) to keep keys secure.

### Testing Your Setup

After setting your API keys, test the LLM integration:

```bash
# Test LLM-generated SPARQL endpoint (uses Anthropic by default)
node test-llm-sparql-generation.js --with-llm
```

## SPARQL Safety & Guardrails

All SPARQL queries are validated before execution:

- **Forbidden operations**: INSERT, DELETE, LOAD, CLEAR, DROP, CREATE, MOVE, COPY, ADD
- **Query type**: Must be SELECT or ASK
- **LIMIT enforcement**: Injected if missing, clamped to `max_limit`
- **SERVICE policy**: Configurable per context pack
  - `allow_any_frink`: Allow SERVICE targeting FRINK-known endpoints
  - `allowlist`: Only allowlisted SERVICE endpoints
  - `forbid_all`: Reject all SERVICE clauses
  - `allow_any`: Allow all (not recommended)

## Development Status

### Phase 1: Foundation & Tool Service API ✅
- [x] Next.js project setup
- [x] Tool Service API routes
- [x] Core libraries (context-packs, SPARQL, LLM providers, budget)
- [x] Basic landing page and chat UI placeholders

### Phase 2: Context Packs & Templates ✅
- [x] Template registry and generator
- [x] Template implementations (dataset_search, entity_lookup)

### Phase 3: Intent Routing & Lane A ✅
- [x] LLM-based intent classification
- [x] Slot filling
- [x] Template → SPARQL generation

### Phase 4: Lane B & C ✅
- [x] LLM-generated SPARQL (Lane B) with guardrails
- [x] SPARQL repair attempts (via modify endpoint)
- [ ] Preflight probes
- [x] User-generated SPARQL editor (Lane C)

### Phase 5: UI Components ✅
- [x] Full chat UI with history
- [x] Inspect drawer (Results, SPARQL, Intent, Context, Ontology, Debug, Plan tabs)
- [x] SPARQL editor (Monaco)
- [x] Results table and download

### Phase 6: LLM Key Management UI (Partial)
- [ ] Settings modal for API keys
- [ ] Shared quota indicator
- [x] Key testing

### Phase 7: Results & Run Records ✅
- [x] Run record persistence
- [x] Results download (CSV/TSV)
- [x] Run summary copy (SPARQL copy implemented)

### Phase 8: Security & Guardrails (Partial)
- [ ] Rate limiting
- [x] Enhanced validation
- [x] Error handling

## Deployment

### Vercel (Recommended)

1. Connect your repository to Vercel
2. Set environment variables in Vercel dashboard
3. Deploy

### Self-Hosted

```bash
npm run build
npm start
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_SHARED_API_KEY` | Shared Anthropic API key (required for LLM features) | - |
| `OPENAI_SHARED_API_KEY` | Shared OpenAI API key (optional) | - |
| `SHARED_BUDGET_USD` | Monthly budget limit for shared keys | 5 |
| `SHARED_BUDGET_STOP_USD` | Budget stop threshold | 4.5 |
| `NEXT_PUBLIC_FRINK_FEDERATION_URL` | FRINK federation endpoint (optional - already configured in context pack) | `https://frink.apps.renci.org/federation/sparql` |
| `USE_JSON_CONTEXT_FOR_PLANNER` | Use `*_global.json` context files instead of YAML metadata for query planning (A/B testing) | `false` |

**Note:** The FRINK endpoint is already configured in `context/packs/wobd.yaml`. You only need to set `NEXT_PUBLIC_FRINK_FEDERATION_URL` if you want to override the default.

## License

Same as parent project.



