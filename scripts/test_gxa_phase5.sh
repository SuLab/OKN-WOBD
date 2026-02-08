#!/usr/bin/env bash
# Test Phase 5 GXA NL routing and slot filling (natural language -> intent -> SPARQL -> execute)
# Requires: web-v2 dev server running (npm run dev), curl, jq
# Run: bash scripts/test_gxa_phase5.sh

set -e

BASE_URL="${BASE_URL:-http://localhost:3000}"

run_nl_query() {
  local text="$1"
  local label="$2"
  local show_slots="${3:-false}"

  echo ""
  echo "=== $label ==="
  echo "Question: $text"

  # 1. Get intent (classifier + slot filler; LLM slot-filler runs when allow_open_nl2sparql)
  INTENT=$(curl -s -X POST "$BASE_URL/api/tools/nl/intent" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg t "$text" '{text: $t, pack_id: "wobd"}')")

  TASK=$(echo "$INTENT" | jq -r '.task')
  echo "Task: $TASK"
  [ "$show_slots" = "true" ] && echo "Slots: $(echo "$INTENT" | jq -c '.slots // {}')"

  # 2. Generate SPARQL
  QUERY=$(echo "$INTENT" | jq -c '{intent: ., pack_id: "wobd"}' | \
    curl -s -X POST "$BASE_URL/api/tools/nl/intent-to-sparql" \
      -H "Content-Type: application/json" \
      -d @- | jq -r '.query')

  if [ -z "$QUERY" ] || [ "$QUERY" = "null" ]; then
    echo "ERROR: Failed to generate query"
    return 1
  fi

  # 3. Execute
  RESP=$(curl -s -X POST "$BASE_URL/api/tools/sparql/execute" \
    -H "Content-Type: application/json" \
    -d "{\"query\": $(echo "$QUERY" | jq -Rs .), \"pack_id\": \"wobd\", \"mode\": \"federated\", \"graphs\": [\"gene-expression-atlas-okn\"]}")

  COUNT=$(echo "$RESP" | jq '.result.results.bindings | length')
  ERR=$(echo "$RESP" | jq -r '.error // empty')
  echo "Count: $COUNT"
  [ -n "$ERR" ] && echo "Error: $ERR"
  echo "First row: $(echo "$RESP" | jq '.result.results.bindings[0]')"
}

echo "Phase 5 GXA NL routing and slot filling tests"
echo "=============================================="

# 1. genes_in_experiment: "genes in E-GEOD-76"
run_nl_query "Which genes are differentially expressed in E-GEOD-76?" "1. Genes in experiment E-GEOD-76"

# 2. experiments_for_gene: "where is DUSP2 upregulated"
run_nl_query "Where is DUSP2 upregulated?" "2. Experiments for gene DUSP2 (upregulated)"

# 3. cross_dataset_summary: "summarize DUSP2 across experiments"
run_nl_query "Summarize DUSP2 differential expression across experiments" "3. Gene cross-dataset summary for DUSP2"

# 4. genes_agreement: "genes upregulated in multiple experiments"
run_nl_query "Find genes upregulated in multiple experiments" "4. Genes agreement (upregulated)"

# 5. genes_discordance: "genes in opposite directions"
run_nl_query "Find genes differentially expressed in opposite directions across contrasts" "5. Genes discordance"

# 6. dataset_search (existing): "gene expression datasets"
run_nl_query "What gene expression datasets exist?" "6. Dataset search (basic)"

echo ""
echo "=== Phase 4 filter extraction (LLM slot-filler) ==="
echo "These require allow_open_nl2sparql and LLM endpoint. Slots shown to verify extraction."
echo ""

# 7. dataset_search + organism: "gene expression datasets in mouse"
run_nl_query "Gene expression datasets in mouse" "7. Dataset search + organism (mouse)" "true"

# 8. dataset_search + disease: "heart disease gene expression datasets"
run_nl_query "What gene expression datasets exist for heart disease?" "8. Dataset search + disease (heart disease)" "true"

# 9. genes_in_experiment + factor: "DE genes in E-GEOD-76 with aortic banding"
run_nl_query "Which genes are DE in E-GEOD-76 with aortic banding?" "9. Genes in experiment + factor (aortic banding)" "true"

echo ""
echo "=== Done ==="
