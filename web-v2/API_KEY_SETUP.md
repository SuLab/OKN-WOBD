# API Key Setup Guide

## Quick Setup

Run the setup script:
```bash
cd web-v2
./setup-env.sh
```

Then edit `.env.local` and add your API keys (Anthropic is now the default LLM provider).

## Anthropic API Key (Default LLM Provider)

**Note:** The app now uses **Claude Sonnet 4.5** by default for all LLM calls. Anthropic API keys are required.

The app supports two ways to provide your Anthropic API key:

### Option 1: Shared Key (Environment Variable) - Recommended for Testing

1. **Create `.env.local` file** in the `web-v2` directory:
   ```bash
   cd web-v2
   ./setup-env.sh  # Creates .env.local with template
   ```

2. **Edit `.env.local`** and add your Anthropic API key:
   ```bash
   ANTHROPIC_SHARED_API_KEY=sk-ant-your-actual-key-here
   ```
   
   Get your key from: https://console.anthropic.com/settings/keys

3. **Restart the dev server** for changes to take effect:
   ```bash
   # Stop the server (Ctrl+C) and restart
   npm run dev
   ```

4. **Test it**:
   ```bash
   node test-llm-sparql-generation.js --with-llm
   ```

### Option 2: BYOK (Bring Your Own Key) - Via Session

If you don't set `ANTHROPIC_SHARED_API_KEY`, you can provide your key through the BYOK system using session IDs. The frontend automatically generates and manages session IDs in localStorage.

**Note:** Server-side LLM calls (like entity identification) require either a shared key or will fail. For full functionality, set `ANTHROPIC_SHARED_API_KEY`.

## OpenAI API Key (Optional - Legacy Support)

The app still supports OpenAI, but it's no longer the default. If you want to use OpenAI instead:

### Option 1: Shared Key (Environment Variable) - Recommended for Testing

1. **Create `.env.local` file** in the `web-v2` directory:
   ```bash
   cd web-v2
   ./setup-env.sh  # Creates .env.local with template
   ```

2. **Edit `.env.local`** and replace `sk-your-key-here` with your actual OpenAI API key:
   ```bash
   OPENAI_SHARED_API_KEY=sk-your-actual-key-here
   ```
   
   Get your key from: https://platform.openai.com/api-keys

3. **Restart the dev server** for changes to take effect:
   ```bash
   # Stop the server (Ctrl+C) and restart
   npm run dev
   ```

4. **Test it**:
   ```bash
   node test-llm-sparql-generation.js --with-llm
   ```

### Option 2: BYOK (Bring Your Own Key) - Via Session

If you don't set `OPENAI_SHARED_API_KEY`, you can provide your key through the BYOK system using session IDs. The frontend automatically generates and manages session IDs in localStorage.

**Note:** Server-side LLM calls (like entity identification) require either a shared key or will fail. For full functionality, set `OPENAI_SHARED_API_KEY`.

## FRINK Endpoint

**Good news: The FRINK endpoint is already configured!** 

The endpoint is set in two places (both already configured):

1. **Context Pack** (`context/packs/wobd.yaml`):
   ```yaml
   federated_endpoint: "https://frink.apps.renci.org/federation/sparql"
   ```

2. **Default in code** (`lib/sparql/executor.ts`):
   ```typescript
   const FRINK_FEDERATION_URL = process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL || 
     "https://frink.apps.renci.org/federation/sparql";
   ```

**You don't need to set anything** unless you want to override it. If you do want to override, add to `.env.local`:
```bash
NEXT_PUBLIC_FRINK_FEDERATION_URL=https://your-custom-frink-endpoint/sparql
```

## Testing with API Keys

### Testing with Anthropic (Default)

Once you've set `ANTHROPIC_SHARED_API_KEY` in `.env.local`:

```bash
# Test LLM-generated SPARQL endpoint (uses Anthropic by default)
node test-llm-sparql-generation.js --with-llm

# Or test manually
curl -X POST http://localhost:3000/api/tools/nl/open-query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Find datasets about COVID-19",
    "pack_id": "wobd",
    "use_shared": true
  }'
```

### Testing with OpenAI (Optional)

If you've set `OPENAI_SHARED_API_KEY` in `.env.local`:

```bash
# Test LLM-generated SPARQL endpoint (specify OpenAI provider)
curl -X POST http://localhost:3000/api/tools/nl/open-query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Find datasets about COVID-19",
    "pack_id": "wobd",
    "provider": "openai",
    "use_shared": true
  }'
```

## Testing with FRINK Endpoint

The FRINK endpoint is already configured, so you can test immediately:

```bash
# Test query execution against FRINK
node test-llm-sparql-generation.js --with-endpoint

# Or test manually
curl -X POST http://localhost:3000/api/tools/sparql/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT ?dataset ?name WHERE { ?dataset a schema:Dataset ; schema:name ?name } LIMIT 10",
    "pack_id": "wobd",
    "mode": "federated",
    "graphs": ["nde"]
  }'
```

## Budget Tracking

Both OpenAI and Anthropic shared keys share the same budget pool (default: $1/month for testing, configurable via `SHARED_BUDGET_USD`). Budget tracking:
- Monitors usage across both providers
- Enforces monthly spending limits
- Resets at the start of each month or on server restart
- Only applies to shared keys (BYOK keys are not tracked)

To adjust the budget limit, set in `.env.local`:
```bash
SHARED_BUDGET_USD=20        # Monthly budget limit (default: $1 for testing)
SHARED_BUDGET_STOP_USD=19.5 # Stop threshold (default: $0.95 for testing)
```

## Summary

- **Anthropic API Key (Required)**: Set `ANTHROPIC_SHARED_API_KEY` in `.env.local` - **This is now the default LLM provider**
- **OpenAI API Key (Optional)**: Set `OPENAI_SHARED_API_KEY` in `.env.local` if you want to use OpenAI instead
- **FRINK Endpoint**: Already configured, no action needed ✅
- **Budget**: Shared budget tracking for both providers (default: $1/month for testing)
- **Restart server**: After setting environment variables, restart `npm run dev`

### Quick Start

1. Run `./setup-env.sh` to create `.env.local`
2. Add your Anthropic API key: `ANTHROPIC_SHARED_API_KEY=sk-ant-...`
3. Restart the dev server: `npm run dev`
4. Start querying! The app will use Claude Sonnet 4.5 by default.
