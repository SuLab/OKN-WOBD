import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { resolveTissueToUberonIds } from "@/lib/ontology";
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

  const organismTaxonIds = parseStringArray(intent.slots?.organism_taxon_ids ?? intent.slots?.species);
  const rawTissue = [
    ...parseStringArray(intent.slots?.tissue_uberon_ids ?? intent.slots?.tissue_iris),
    ...parseStringArray(intent.slots?.tissue_uberon_ids_ols),
  ];
  const tissueUberonIds = await resolveTissueToUberonIds(rawTissue);
  const factorTerms = parseStringArray(intent.slots?.factor_terms ?? intent.slots?.perturbation);
  // Optional: OKN data differs from live GXA, so no default filters; users can add min_abs_log2fc, max_adj_p_value to align
  const minAbsLog2fc = intent.slots?.min_abs_log2fc != null ? Number(intent.slots.min_abs_log2fc) : undefined;
  const maxAdjPValue = intent.slots?.max_adj_p_value != null ? Number(intent.slots.max_adj_p_value) : undefined;

  return buildGXAGenesForExperimentQuery(
    experimentId,
    capped,
    upregulated,
    organismTaxonIds.length > 0 ? organismTaxonIds : undefined,
    tissueUberonIds.length > 0 ? tissueUberonIds : undefined,
    factorTerms.length > 0 ? factorTerms : undefined,
    minAbsLog2fc,
    maxAdjPValue
  );
}

function parseStringArray(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean);
  if (typeof raw === "string") return raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  return [];
}

