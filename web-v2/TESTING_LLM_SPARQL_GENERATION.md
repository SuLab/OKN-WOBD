# LLM SPARQL Generation Testing Guide

This guide covers testing all LLM SPARQL Generation (Lane B) components.

## Prerequisites

1. **Server Running**: Make sure the Next.js dev server is running:
   ```bash
   cd web-v2
   npm run dev
   ```

2. **Environment Variables** (optional, for full testing):
   ```bash
   export ANTHROPIC_SHARED_API_KEY="sk-ant-..."  # For LLM-generated SPARQL tests (default)
   export OPENAI_SHARED_API_KEY="sk-..."  # Alternative: OpenAI
   ```

## Automated Tests

Run the test script:

```bash
cd web-v2

# Basic tests (no LLM or endpoint required)
node test-llm-sparql-generation.js

# With LLM tests (requires API key)
node test-llm-sparql-generation.js --with-llm

# With endpoint tests (tests against FRINK)
node test-llm-sparql-generation.js --with-endpoint

# Full test suite
node test-llm-sparql-generation.js --with-llm --with-endpoint
```

## Manual Testing Checklist

### 1. LLM-Generated SPARQL Endpoint (Lane B)

**Test via curl:**
```bash
curl -X POST http://localhost:3000/api/tools/nl/open-query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Find datasets about COVID-19",
    "pack_id": "wobd",
    "use_shared": true
  }'
```

**Expected:**
- Returns valid SPARQL query
- Query includes SELECT or ASK
- Validation passes
- Includes usage metadata

**Test with BYOK:**
```bash
# First set a key (if you have a test endpoint for this)
# Then test with session_id
curl -X POST http://localhost:3000/api/tools/nl/open-query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Find datasets about diabetes",
    "pack_id": "wobd",
    "session_id": "test-123",
    "provider": "anthropic",
    "model": "claude-sonnet-4-5"
  }'
```

### 2. SPARQL Repair

**Test repair logic:**
```bash
# Test repair function directly (if you have a Node REPL or test file)
# Or test via execution endpoint with a query that might fail
```

**Verify repair strategies:**
- Removes overly specific FILTER clauses
- Switches exact string match to regex
- Removes excessive OPTIONAL clauses
- Increases small LIMIT values

### 3. Query Execution with Repair & Preflight

**Test execution with repair:**
```bash
curl -X POST http://localhost:3000/api/tools/sparql/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT ?dataset ?name WHERE { ?dataset a schema:Dataset ; schema:name ?name } LIMIT 10",
    "pack_id": "wobd",
    "mode": "federated",
    "graphs": ["nde"],
    "attempt_repair": true,
    "run_preflight": true
  }'
```

**Expected:**
- Query executes successfully
- If error occurs, repair is attempted
- Preflight results included (if enabled)
- Run record includes repair/preflight metadata

### 4. User-Generated SPARQL Editor (Lane C)

**Manual UI Testing:**

1. Navigate to `http://localhost:3000/chat`
2. Type `/sparql` in the input
3. Verify:
   - ✅ Input switches to Monaco editor
   - ✅ Lane indicator shows "User-Generated SPARQL (Lane C)"
   - ✅ Syntax highlighting works
   - ✅ Cmd/Ctrl + Enter executes query
   - ✅ Editor is responsive

**Test SPARQL input:**
```sparql
PREFIX schema: <http://schema.org/>
SELECT ?dataset ?name
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
}
LIMIT 10
```

### 5. Chat Composer Lane Switching

**Test Lane Detection:**

1. **Lane A (Template-based SPARQL):**
   - Type: "Find datasets about diabetes"
   - Verify: Shows "Template-based SPARQL (Lane A)" indicator

2. **Lane B (LLM-generated SPARQL):**
   - Type: "/open Find datasets about COVID-19"
   - Verify: Shows "LLM-generated SPARQL (Lane B)" indicator

3. **Lane C (User-generated SPARQL):**
   - Type: "/sparql SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"
   - Verify: Shows "User-Generated SPARQL (Lane C)" indicator and Monaco editor

**Test Lane Switching:**
- Start in one lane, switch to another
- Verify UI updates correctly
- Verify state is preserved when switching back

### 6. Intent Classification

**Test intent routing:**
```bash
curl -X POST http://localhost:3000/api/tools/nl/intent \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Find datasets about diabetes",
    "pack_id": "wobd"
  }'
```

**Expected:**
- Returns intent with `task`, `lane`, `confidence`
- Routes to appropriate lane based on confidence
- Includes slot information

### 7. SPARQL Validation

**Test validation:**
```bash
curl -X POST http://localhost:3000/api/tools/sparql/validate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"
  }'
```

**Test forbidden operations:**
```bash
curl -X POST http://localhost:3000/api/tools/sparql/validate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "INSERT DATA { <s> <p> <o> }"
  }'
```

**Expected:**
- Valid queries pass
- Forbidden operations are rejected
- LIMIT injection works for queries without LIMIT

## Integration Testing

### End-to-End Flow: Template-based SPARQL (Lane A)

1. User types: "Find datasets about diabetes"
2. Intent classification routes to template lane
3. Template generates SPARQL
4. Query executes with FROM clauses
5. Results returned

### End-to-End Flow: LLM-Generated SPARQL (Lane B)

1. User types: "/open Find datasets about COVID-19"
2. Intent classification routes to LLM-generated lane
3. LLM generates SPARQL
4. Query validated and executed
5. Results returned

### End-to-End Flow: User-Generated SPARQL (Lane C)

1. User types: "/sparql SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"
2. SPARQL editor appears
3. User submits query
4. Query validated and executed
5. Results returned

## Query Types Overview

The system supports three types of SPARQL query generation:

1. **Template-based SPARQL (Lane A)**: LLM outputs intent JSON, app generates SPARQL from vetted templates
   - Most reliable and predictable
   - Uses predefined templates with slots
   - Fast and cost-effective

2. **LLM-generated SPARQL (Lane B)**: LLM generates SPARQL directly from natural language
   - More flexible for novel queries
   - Constrained by context pack schema hints
   - Requires LLM API calls

3. **User-generated SPARQL (Lane C)**: User directly writes/pastes SPARQL
   - Full control for expert users
   - No LLM involved
   - Requires SPARQL knowledge

## Known Limitations

1. **Monaco Editor**: SPARQL language support is basic (no custom language definition yet)
2. **Preflight**: May be slow against real endpoints
3. **Repair**: Only attempts one repair, doesn't retry multiple strategies
4. **Error Handling**: Some edge cases may need better error messages

## Next Steps After Testing

Once all tests pass:
1. Fix any issues found
2. Document any limitations
3. Proceed to Phase 5: UI Components
