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

function parseStringArray(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.map((x) => String(x).trim()).filter(Boolean);
  }
  if (typeof raw === "string") {
    return raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

export async function buildGeneExpressionDatasetSearchQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const limit = (intent.slots?.limit as number) ?? GXA_COVERAGE_DEFAULT_LIMIT;
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 500);

  // Phase 4: ontology-grounded context filters
  const organismTaxonIds = parseStringArray(intent.slots?.organism_taxon_ids ?? intent.slots?.species);
  const rawTissue = parseStringArray(intent.slots?.tissue_uberon_ids ?? intent.slots?.tissue_iris);
  const tissueUberonIds = rawTissue
    .map((t) => {
      const fromIri = t.match(/UBERON_([\d]+)$/i)?.[1];
      const fromCurie = t.match(/UBERON[_\s:]*([\d]+)/i)?.[1];
      return fromIri ?? fromCurie ?? t.replace(/^UBERON[_\s:]*/i, "").replace(/^http:\/\/purl\.obolibrary\.org\/obo\/UBERON_/i, "");
    })
    .filter(Boolean);
  const factorTerms = parseStringArray(intent.slots?.factor_terms ?? intent.slots?.perturbation);
  const rawDisease = parseStringArray(intent.slots?.disease_efo_ids ?? intent.slots?.disease_iris);
  const diseaseEfoIds = rawDisease
    .map((d) => d.replace(/^EFO_?/i, "").replace(/^http:\/\/www\.ebi\.ac\.uk\/efo\/EFO_/i, "").trim())
    .filter(Boolean);

  return buildGXAExperimentCoverageQuery(
    capped,
    organismTaxonIds.length > 0 ? organismTaxonIds : undefined,
    tissueUberonIds.length > 0 ? tissueUberonIds : undefined,
    factorTerms.length > 0 ? factorTerms : undefined,
    diseaseEfoIds.length > 0 ? diseaseEfoIds : undefined
  );
}
