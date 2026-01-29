import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildGXAGenesDiscordanceQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_GENES_DISCORDANCE_TEMPLATE_ID =
  "gene_expression_genes_discordance";

export const geneExpressionGenesDiscordanceTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_GENES_DISCORDANCE_TEMPLATE_ID,
  description:
    "Find genes differentially expressed in opposite directions across contrasts",
  required_slots: [],
};

export async function buildGeneExpressionGenesDiscordanceQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const limit =
    ((intent.slots?.limit as number) || pack.guardrails?.max_limit) ?? 50;
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 200);

  return buildGXAGenesDiscordanceQuery(capped);
}
