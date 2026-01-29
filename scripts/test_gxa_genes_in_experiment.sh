#!/usr/bin/env bash
# Test gene_expression_genes_in_experiment flow: intent-to-sparql -> execute -> optional direct FRINK test
# Requires: web-v2 dev server running (npm run dev), curl, jq

set -e

BASE_URL="${BASE_URL:-http://localhost:3000}"
FRINK_GXA="${FRINK_GXA:-https://frink.apps.renci.org/gene-expression-atlas-okn/sparql}"

echo "=== 1. Generate SPARQL via intent-to-sparql ==="
QUERY=$(curl -s -X POST "$BASE_URL/api/tools/nl/intent-to-sparql" \
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

if [ -z "$QUERY" ] || [ "$QUERY" = "null" ]; then
  echo "ERROR: Failed to generate query"
  exit 1
fi
echo "Query generated ($(echo -n "$QUERY" | wc -c | tr -d ' ') chars)"

echo ""
echo "=== 2. Execute via app (with debug) ==="
RESP=$(curl -s -X POST "$BASE_URL/api/tools/sparql/execute" \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(echo "$QUERY" | jq -Rs .), \"pack_id\": \"wobd\", \"mode\": \"federated\", \"graphs\": [\"gene-expression-atlas-okn\"], \"debug\": true}")

COUNT=$(echo "$RESP" | jq '.result.results.bindings | length')
ERROR=$(echo "$RESP" | jq -r '.error // empty')
ENDPOINT=$(echo "$RESP" | jq -r '.endpoint_used // empty')

echo "Count: $COUNT"
echo "Endpoint: $ENDPOINT"
[ -n "$ERROR" ] && echo "Error: $ERROR"

EXECUTED=$(echo "$RESP" | jq -r '.executed_query // empty')
if [ -n "$EXECUTED" ]; then
  echo "$EXECUTED" > /tmp/gxa_query.sparql
  echo "Executed query saved to /tmp/gxa_query.sparql"
fi

echo ""
echo "=== 3. Run executed query directly against FRINK (if debug was used) ==="
if [ -f /tmp/gxa_query.sparql ]; then
  DIRECT_COUNT=$(curl -s -X POST "$FRINK_GXA" \
    -H "Content-Type: application/sparql-query" \
    -H "Accept: application/sparql-results+json" \
    --data-binary @/tmp/gxa_query.sparql | jq '.results.bindings | length')
  echo "Direct FRINK count: $DIRECT_COUNT"
  if [ "$DIRECT_COUNT" != "null" ] && [ "$DIRECT_COUNT" -gt 0 ] && [ "$COUNT" = "0" ]; then
    echo "NOTE: Direct FRINK returns $DIRECT_COUNT rows but app returned 0 - check app execution path"
  fi
else
  echo "Skipped (no executed_query in response)"
fi

echo ""
echo "=== Done ==="
