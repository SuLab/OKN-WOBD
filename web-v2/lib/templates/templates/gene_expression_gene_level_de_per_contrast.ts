import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { resolveTissueToUberonIds } from "@/lib/ontology";
import { isEnsemblGeneStableId } from "@/lib/ontology/gene-identifiers";
import { buildGXAExperimentsForGenesQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_GENE_LEVEL_DE_PER_CONTRAST_TEMPLATE_ID =
  "gene_expression_gene_level_de_per_contrast";

export const geneExpressionGeneLevelDePerContrastTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_GENE_LEVEL_DE_PER_CONTRAST_TEMPLATE_ID,
  description:
    "Gene-level differential expression per contrast: gene(s), contrasts, direction (up/down), and metrics across GXA experiments",
  required_slots: ["gene_symbols"],
};

export async function buildGeneExpressionGeneLevelDePerContrastQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  const rawSymbols = intent.slots?.gene_symbols;

  let geneSymbols: string[] = [];
  if (Array.isArray(rawSymbols)) {
    geneSymbols = rawSymbols.map((s) => String(s).trim()).filter(Boolean);
  } else if (typeof rawSymbols === "string") {
    geneSymbols = rawSymbols
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const symbols: string[] = [];
  const ensemblGeneIds: string[] = [];
  for (const t of geneSymbols) {
    if (isEnsemblGeneStableId(t)) {
      ensemblGeneIds.push(t.trim().toUpperCase());
    } else {
      symbols.push(t);
    }
  }

  if (symbols.length === 0 && ensemblGeneIds.length === 0) {
    throw new Error(
      "gene_symbols slot is required for gene_expression_gene_level_de_per_contrast"
    );
  }

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

  return buildGXAExperimentsForGenesQuery(
    symbols,
    capped,
    upregulated,
    organismTaxonIds.length > 0 ? organismTaxonIds : undefined,
    tissueUberonIds.length > 0 ? tissueUberonIds : undefined,
    factorTerms.length > 0 ? factorTerms : undefined,
    true,
    ensemblGeneIds
  );
}

function parseStringArray(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean);
  if (typeof raw === "string") return raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  return [];
}
