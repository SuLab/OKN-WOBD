#!/usr/bin/env bash
# Test Phase 3 GXA cross-dataset templates: summary, agreement, discordance
# Requires: web-v2 dev server running (npm run dev), curl, jq

set -e

BASE_URL="${BASE_URL:-http://localhost:3000}"

run_task() {
  local task="$1"
  local slots="$2"
  local label="$3"

  echo ""
  echo "=== $label ($task) ==="
  QUERY=$(curl -s -X POST "$BASE_URL/api/tools/nl/intent-to-sparql" \
    -H "Content-Type: application/json" \
    -d "{
      \"intent\": {
        \"task\": \"$task\",
        \"context_pack\": \"wobd\",
        \"lane\": \"template\",
        \"graph_mode\": \"federated\",
        \"graphs\": [\"gene-expression-atlas-okn\"],
        \"slots\": $slots
      },
      \"pack_id\": \"wobd\"
    }" | jq -r '.query')

  if [ -z "$QUERY" ] || [ "$QUERY" = "null" ]; then
    echo "ERROR: Failed to generate query"
    return 1
  fi

  RESP=$(curl -s -X POST "$BASE_URL/api/tools/sparql/execute" \
    -H "Content-Type: application/json" \
    -d "{\"query\": $(echo "$QUERY" | jq -Rs .), \"pack_id\": \"wobd\", \"mode\": \"federated\", \"graphs\": [\"gene-expression-atlas-okn\"]}")

  COUNT=$(echo "$RESP" | jq '.result.results.bindings | length')
  ENDPOINT=$(echo "$RESP" | jq -r '.endpoint_used // empty')
  ERR=$(echo "$RESP" | jq -r '.error // empty')
  echo "Count: $COUNT"
  echo "Endpoint: $ENDPOINT"
  [ -n "$ERR" ] && echo "Error: $ERR"
  echo "First row: $(echo "$RESP" | jq '.result.results.bindings[0]')"
}

echo "Phase 3 GXA cross-dataset tests"
echo "=============================="

run_task "gene_expression_gene_cross_dataset_summary" '{"gene_symbol": "DUSP2", "limit": 20}' "1. Gene cross-dataset summary (DUSP2)"
run_task "gene_expression_genes_agreement" '{"min_experiments": 2, "direction": "up", "limit": 20}' "2. Genes agreement (up, >=2 experiments)"
run_task "gene_expression_genes_discordance" '{"limit": 20}' "3. Genes discordance"

# Debug: capture executed query for discordance and run directly against FRINK
echo ""
echo "=== 4. Debug: run discordance with debug, compare to direct FRINK ==="
QUERY=$(curl -s -X POST "$BASE_URL/api/tools/nl/intent-to-sparql" \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "task": "gene_expression_genes_discordance",
      "context_pack": "wobd",
      "lane": "template",
      "graph_mode": "federated",
      "graphs": ["gene-expression-atlas-okn"],
      "slots": {"limit": 20}
    },
    "pack_id": "wobd"
  }' | jq -r '.query')
EXEC_RESP=$(curl -s -X POST "$BASE_URL/api/tools/sparql/execute" \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(echo "$QUERY" | jq -Rs .), \"pack_id\": \"wobd\", \"mode\": \"federated\", \"graphs\": [\"gene-expression-atlas-okn\"], \"debug\": true}")
EXECUTED=$(echo "$EXEC_RESP" | jq -r '.executed_query')
APP_COUNT=$(echo "$EXEC_RESP" | jq '.result.results.bindings | length')
  echo "App count: $APP_COUNT"
  if [ -n "$EXECUTED" ] && [ "$EXECUTED" != "null" ]; then
    echo "$EXECUTED" > /tmp/discordance_executed.sparql
  DIRECT_COUNT=$(curl -s -X POST https://frink.apps.renci.org/gene-expression-atlas-okn/sparql \
    -H "Content-Type: application/sparql-query" \
    -H "Accept: application/sparql-results+json" \
    --data-binary @/tmp/discordance_executed.sparql | jq '.results.bindings | length')
  echo "Direct FRINK count (same query): $DIRECT_COUNT"
  if [ "$APP_COUNT" != "$DIRECT_COUNT" ]; then
    echo "MISMATCH: app=$APP_COUNT, direct=$DIRECT_COUNT"
  fi
fi

echo ""
echo "=== Done ==="
