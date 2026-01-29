import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildGXAGeneCrossDatasetSummaryQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_GENE_CROSS_DATASET_SUMMARY_TEMPLATE_ID =
  "gene_expression_gene_cross_dataset_summary";

export const geneExpressionGeneCrossDatasetSummaryTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_GENE_CROSS_DATASET_SUMMARY_TEMPLATE_ID,
  description:
    "Summarize a gene's differential expression evidence across experiments (per contrast)",
  required_slots: ["gene_symbol"],
};

export async function buildGeneExpressionGeneCrossDatasetSummaryQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const raw = intent.slots?.gene_symbol;
  const geneSymbol =
    typeof raw === "string"
      ? raw.trim()
      : Array.isArray(raw)
        ? String(raw[0] ?? "").trim()
        : "";
  if (!geneSymbol) {
    throw new Error(
      "gene_symbol slot is required for gene_expression_gene_cross_dataset_summary"
    );
  }

  const limit =
    ((intent.slots?.limit as number) || pack.guardrails?.max_limit) ?? 100;
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 500);

  return buildGXAGeneCrossDatasetSummaryQuery(geneSymbol, capped);
}
