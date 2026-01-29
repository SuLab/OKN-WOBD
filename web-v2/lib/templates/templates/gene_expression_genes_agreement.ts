import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildGXAGenesAgreementQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID =
  "gene_expression_genes_agreement";

export const geneExpressionGenesAgreementTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID,
  description:
    "Find genes differentially expressed in the same direction across multiple experiments",
  required_slots: [],
};

export async function buildGeneExpressionGenesAgreementQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const minExperiments =
    (intent.slots?.min_experiments as number) ?? 2;
  const direction = (intent.slots?.direction as string | undefined)?.toLowerCase();
  const dir =
    direction === "up" || direction === "upregulated"
      ? ("up" as const)
      : direction === "down" || direction === "downregulated"
        ? ("down" as const)
        : undefined;

  const limit =
    ((intent.slots?.limit as number) || pack.guardrails?.max_limit) ?? 50;
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 200);

  return buildGXAGenesAgreementQuery(minExperiments, dir, capped);
}
