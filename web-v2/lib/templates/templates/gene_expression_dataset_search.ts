import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildGXAExperimentCoverageQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_DATASET_SEARCH_TEMPLATE_ID = "gene_expression_dataset_search";

export const geneExpressionDatasetSearchTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_DATASET_SEARCH_TEMPLATE_ID,
  description: "List gene expression experiments (datasets) that have differential expression results",
  required_slots: [],
};

// Lower default limit for GXA coverage so the slow direct endpoint returns in reasonable time (~20–30s vs ~80s for 500).
const GXA_COVERAGE_DEFAULT_LIMIT = 50;

export async function buildGeneExpressionDatasetSearchQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const limit = (intent.slots?.limit as number) ?? GXA_COVERAGE_DEFAULT_LIMIT;
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 500);
  return buildGXAExperimentCoverageQuery(capped);
}
