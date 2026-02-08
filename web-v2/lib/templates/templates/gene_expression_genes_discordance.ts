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

  return buildGXAGenesDiscordanceQuery(
    capped,
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
