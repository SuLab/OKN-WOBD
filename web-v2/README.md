# WOBD Web v2

Exa-style chat UI for WOBD with template-based, LLM-generated, and user-generated SPARQL querying. This is a Next.js application that provides a provider-neutral Tool Service API and a modern web interface for querying biomedical datasets.

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

1. Copy `.env.example` to `.env.local`:
   ```bash
   cp .env.example .env.local
   ```

2. Set your environment variables:
   ```bash
   OPENAI_SHARED_API_KEY=sk-...  # Optional: for shared OpenAI usage
   SHARED_BUDGET_USD=20
   SHARED_BUDGET_STOP_USD=19.5
   NEXT_PUBLIC_FRINK_FEDERATION_URL=https://frink.apps.renci.org/federation/sparql
   ```

### Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

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

## Chat Commands

The chat interface supports special `@` commands for graph discovery and query suggestions:

### Graph Commands
- `@graph` or `@graphs` - List all available graphs in FRINK Federated SPARQL with descriptions
- `@graph <shortname>` - Get detailed information about a specific graph (e.g., `@graph nde`)
  - Shows graph IRI, endpoint, description, and usage instructions

### Query Suggestions
- `@suggest` or `@suggestions` - Get query/topic suggestions for all graphs (quick mode)
- `@suggest <shortname>` - Get query suggestions for a specific graph (e.g., `@suggest nde`)
  - Provides topic suggestions based on graph content
  - Includes example SPARQL queries
  - Uses quick mode by default (based on graph descriptions)
  - Full mode available via API for schema-based suggestions

### Mode Switching
- `/text` or `/open` - Switch to LLM-generated SPARQL mode (Lane B - LLM generates SPARQL directly)
- `/sparql` - Switch to User-generated SPARQL editor mode (Lane C - write SPARQL directly)

## Tool Service API

The Tool Service API provides stable HTTP endpoints for all WOBD operations:

### Registry / Graph Discovery
- `GET /api/tools/registry/graphs` - List available graphs
- `GET /api/tools/graphs/info?shortname=<name>` - Get graph details
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

WOBD Web v2 supports two modes:

1. **Shared OpenAI Key** (limited free usage)
   - Configured via `OPENAI_SHARED_API_KEY` environment variable
   - Enforced $20/month budget cap (configurable)
   - Budget tracked server-side

2. **Bring Your Own Key (BYOK)**
   - Supports OpenAI, Anthropic, and Gemini
   - Keys stored in session (not persisted)
   - No budget limits for BYOK usage

All LLM calls are proxied through the backend (`/api/tools/llm/complete`) to keep keys secure.

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

### Phase 2: Context Packs & Templates (In Progress)
- [ ] Template registry and generator
- [ ] Template implementations (dataset_search, entity_lookup)

### Phase 3: Intent Routing & Lane A
- [ ] LLM-based intent classification
- [ ] Slot filling
- [ ] Template → SPARQL generation

### Phase 4: Lane B & C
- [ ] LLM-generated SPARQL (Lane B) with guardrails
- [ ] SPARQL repair attempts
- [ ] Preflight probes
- [ ] User-generated SPARQL editor (Lane C)

### Phase 5: UI Components
- [ ] Full chat UI with history
- [ ] Inspect drawer (Results, SPARQL, Intent, Context, Debug tabs)
- [ ] SPARQL editor (Monaco)
- [ ] Results table and download

### Phase 6: LLM Key Management UI
- [ ] Settings modal for API keys
- [ ] Shared quota indicator
- [ ] Key testing

### Phase 7: Results & Run Records
- [ ] Run record persistence
- [ ] Results download (CSV/TSV)
- [ ] Run summary copy

### Phase 8: Security & Guardrails
- [ ] Rate limiting
- [ ] Enhanced validation
- [ ] Error handling

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
| `OPENAI_SHARED_API_KEY` | Shared OpenAI API key | - |
| `SHARED_BUDGET_USD` | Monthly budget limit | 20 |
| `SHARED_BUDGET_STOP_USD` | Budget stop threshold | 19.5 |
| `NEXT_PUBLIC_FRINK_FEDERATION_URL` | FRINK federation endpoint | `https://frink.apps.renci.org/federation/sparql` |

## License

Same as parent project.



