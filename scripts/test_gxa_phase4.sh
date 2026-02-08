#!/usr/bin/env bash
# Test Phase 4 GXA contextual filters (organism, tissue, factor)
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

echo "Phase 4 GXA contextual filter tests"
echo "==================================="

# 1. Dataset search with organism filter (10090 = Mus musculus)
run_task "gene_expression_dataset_search" '{"organism_taxon_ids": "10090", "limit": 10}' "1. Dataset search (organism=10090)"

# 2. Dataset search with factor term (may timeout: CONTAINS is expensive on large graphs)
# Note: factor_terms uses plain text CONTAINS; "surgery" appears in FRINK but query can hit 120s timeout
run_task "gene_expression_dataset_search" '{"factor_terms": "surgery", "limit": 10}' "2. Dataset search (factor=surgery) [may timeout]"

# 3. Genes in experiment with organism filter (E-GEOD-76 is mouse/10090; E-GEOD-23301 is Arabidopsis/3702)
run_task "gene_expression_genes_in_experiment" '{"experiment_id": "E-GEOD-76", "organism_taxon_ids": "10090", "limit": 20}' "3. Genes in experiment E-GEOD-76 (organism=10090)"

# 4. Experiments for gene with factor filter (may timeout)
run_task "gene_expression_experiments_for_gene" '{"gene_symbols": "DUSP2", "factor_terms": "surgery", "limit": 20}' "4. Experiments for gene (factor=surgery) [may timeout]"

# 5. Cross-dataset summary with organism filter
run_task "gene_expression_gene_cross_dataset_summary" '{"gene_symbol": "DUSP2", "organism_taxon_ids": "10090", "limit": 20}' "5. Gene cross-dataset summary (organism=10090)"

# 6. Agreement with organism filter
run_task "gene_expression_genes_agreement" '{"min_experiments": 2, "direction": "up", "organism_taxon_ids": "10090", "limit": 20}' "6. Genes agreement (organism=10090)"

# 7. Discordance with organism filter
run_task "gene_expression_genes_discordance" '{"organism_taxon_ids": "10090", "limit": 20}' "7. Genes discordance (organism=10090)"

echo ""
echo "=== Done ==="
