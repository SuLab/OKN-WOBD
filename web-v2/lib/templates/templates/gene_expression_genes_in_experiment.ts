import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildGXAGenesForExperimentQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_GENES_IN_EXPERIMENT_TEMPLATE_ID =
  "gene_expression_genes_in_experiment";

export const geneExpressionGenesInExperimentTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_GENES_IN_EXPERIMENT_TEMPLATE_ID,
  description:
    "List differentially expressed genes for a given gene expression experiment (per contrast)",
  required_slots: ["experiment_id"],
};

export async function buildGeneExpressionGenesInExperimentQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const experimentId = (intent.slots?.experiment_id as string)?.trim();
  if (!experimentId) {
    throw new Error(
      "experiment_id slot is required for gene_expression_genes_in_experiment"
    );
  }

  // Optional direction slot: "up", "down", or undefined
  const direction = (intent.slots?.direction as string | undefined)?.toLowerCase();
  let upregulated: boolean | undefined = undefined;
  if (direction === "up" || direction === "upregulated") {
    upregulated = true;
  } else if (direction === "down" || direction === "downregulated") {
    upregulated = false;
  }

  const limit =
    ((intent.slots?.limit as number) || pack.guardrails?.max_limit) ?? 100;
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 500);

  return buildGXAGenesForExperimentQuery(experimentId, capped, upregulated);
}

