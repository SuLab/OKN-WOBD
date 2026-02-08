import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildGXAExperimentsForGenesQuery } from "@/lib/ontology/templates";

export const GENE_EXPRESSION_EXPERIMENTS_FOR_GENE_TEMPLATE_ID =
  "gene_expression_experiments_for_gene";

export const geneExpressionExperimentsForGeneTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_EXPERIMENTS_FOR_GENE_TEMPLATE_ID,
  description:
    "Find gene expression experiments/contrasts where a gene is differentially expressed",
  required_slots: ["gene_symbols"],
};

export async function buildGeneExpressionExperimentsForGeneQuery(
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

  if (geneSymbols.length === 0) {
    throw new Error(
      "gene_symbols slot is required for gene_expression_experiments_for_gene"
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
  const rawTissue = parseStringArray(intent.slots?.tissue_uberon_ids ?? intent.slots?.tissue_iris);
  const tissueUberonIds = rawTissue
    .map((t) => {
      const fromIri = t.match(/UBERON_([\d]+)$/i)?.[1];
      const fromCurie = t.match(/UBERON[_\s:]*([\d]+)/i)?.[1];
      return fromIri ?? fromCurie ?? t.replace(/^UBERON[_\s:]*/i, "").replace(/^http:\/\/purl\.obolibrary\.org\/obo\/UBERON_/i, "");
    })
    .filter(Boolean);
  const factorTerms = parseStringArray(intent.slots?.factor_terms ?? intent.slots?.perturbation);

  return buildGXAExperimentsForGenesQuery(
    geneSymbols,
    capped,
    upregulated,
    organismTaxonIds.length > 0 ? organismTaxonIds : undefined,
    tissueUberonIds.length > 0 ? tissueUberonIds : undefined,
    factorTerms.length > 0 ? factorTerms : undefined
  );
}

function parseStringArray(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean);
  if (typeof raw === "string") return raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  return [];
}

