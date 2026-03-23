import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { resolveTissueToUberonIds } from "@/lib/ontology";
import {
  buildGXAGenesAgreementQuery,
  buildNDEDiseaseCoverageQuery,
} from "@/lib/ontology/templates";
import { expandMondoToDescendants } from "@/lib/ontology/mondo-descendants";
import { resolveMondoToEfo } from "@/lib/ontology/mondo-to-efo";

export const GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID =
  "gene_expression_genes_agreement";

export const geneExpressionGenesAgreementTemplate: TemplateDefinition = {
  id: GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID,
  description:
    "Find genes differentially expressed in the same direction across multiple experiments",
  required_slots: ["organism_taxon_ids"],
  optional_slots: ["min_experiments", "direction", "limit", "tissue_uberon_ids_ols", "factor_terms", "health_conditions", "expand_mondo_descendants"],
};

export interface GeneExpressionGenesAgreementResult {
  query: string;
  relatedQueries?: { nde_disease_coverage?: string };
}

export async function buildGeneExpressionGenesAgreementQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string | GeneExpressionGenesAgreementResult> {
  const minExperimentsRaw = intent.slots?.min_experiments;
  const minExperiments =
    typeof minExperimentsRaw === "number"
      ? minExperimentsRaw
      : typeof minExperimentsRaw === "string" && minExperimentsRaw.trim() !== ""
        ? Math.max(1, parseInt(minExperimentsRaw.trim(), 10) || 2)
        : 2;
  const direction = (intent.slots?.direction as string | undefined)?.toLowerCase();
  const dir =
    direction === "up" || direction === "upregulated"
      ? ("up" as const)
      : direction === "down" || direction === "downregulated"
        ? ("down" as const)
        : undefined;

  const limitRaw = intent.slots?.limit;
  const limit =
    typeof limitRaw === "number"
      ? limitRaw
      : typeof limitRaw === "string" && limitRaw.trim() !== ""
        ? parseInt(limitRaw.trim(), 10) || (pack.guardrails?.max_limit ?? 50)
        : (pack.guardrails?.max_limit ?? 50);
  const capped = Math.min(limit, pack.guardrails?.max_limit ?? 200);

  const organismTaxonIds = parseStringArray(intent.slots?.organism_taxon_ids ?? intent.slots?.species);
  const rawTissue = [
    ...parseStringArray(intent.slots?.tissue_uberon_ids ?? intent.slots?.tissue_iris),
    ...parseStringArray(intent.slots?.tissue_uberon_ids_ols),
  ];
  const tissueUberonIds = await resolveTissueToUberonIds(rawTissue);
  const factorTerms = parseStringArray(intent.slots?.factor_terms ?? intent.slots?.perturbation);

  const ubergraphEndpoint = pack.endpoint_mode?.direct_endpoints?.ubergraph;

  // Ontology-driven path: disease from health_conditions or ontology_state
  const healthConditions = intent.slots?.health_conditions as string[] | undefined;
  const ontologyState = intent.slots?.ontology_state as
    | { grounded_mondo_terms?: Array<{ mondo?: string }> }
    | undefined;
  const groundedMondo = ontologyState?.grounded_mondo_terms
    ?.map((t) => t.mondo)
    .filter((iri): iri is string => Boolean(iri));
  const rawMondo = Array.isArray(healthConditions) && healthConditions.length > 0
    ? healthConditions
    : groundedMondo && groundedMondo.length > 0
      ? groundedMondo
      : [];
  // Normalize CURIEs (e.g. MONDO:0005015) to full IRIs for resolveMondoToEfo / expandMondoToDescendants
  const mondoIRIsFromIntent = rawMondo.map(normalizeMondoToIri).filter(Boolean);

  const expandDescendants =
    intent.slots?.expand_mondo_descendants === true ||
    intent.slots?.expand_mondo_descendants === "true" ||
    intent.slots?.expand_mondo_descendants === "1";

  let diseaseIris: string[] = [];
  let mondoIRIsForNDE: string[] = [];

  if (mondoIRIsFromIntent.length > 0) {
    let mondoIRIsToUse = mondoIRIsFromIntent;
    if (expandDescendants && ubergraphEndpoint) {
      try {
        mondoIRIsToUse = await expandMondoToDescendants(mondoIRIsFromIntent, {
          maxTerms: 200,
          endpoint: ubergraphEndpoint,
        });
      } catch (err) {
        console.warn("[gene_expression_genes_agreement] MONDO expansion failed, using root only:", err);
      }
    }
    mondoIRIsForNDE = mondoIRIsToUse;

    if (ubergraphEndpoint) {
      try {
        const { efoIris } = await resolveMondoToEfo(mondoIRIsToUse, {
          ubergraphEndpoint,
          useOLSFallback: true,
        });
        if (efoIris.length > 0) diseaseIris.push(...efoIris);
      } catch (err) {
        console.warn("[gene_expression_genes_agreement] MONDO→EFO resolution failed:", err);
      }
    }
    diseaseIris.push(...mondoIRIsToUse);
  }

  const diseaseIrisForQuery = [...new Set(diseaseIris)];

  // Default direction to "up" when disease context (consistently upregulated)
  const effectiveDirection = dir ?? (mondoIRIsFromIntent.length > 0 ? "up" : undefined);

  const query = buildGXAGenesAgreementQuery(
    minExperiments,
    effectiveDirection,
    capped,
    organismTaxonIds.length > 0 ? organismTaxonIds : undefined,
    tissueUberonIds.length > 0 ? tissueUberonIds : undefined,
    factorTerms.length > 0 ? factorTerms : undefined,
    diseaseIrisForQuery.length > 0 ? diseaseIrisForQuery : undefined
  );

  const ndeQuery =
    mondoIRIsForNDE.length > 0 ? buildNDEDiseaseCoverageQuery(mondoIRIsForNDE) : "";

  if (ndeQuery) {
    return { query, relatedQueries: { nde_disease_coverage: ndeQuery } };
  }
  return query;
}

function parseStringArray(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean);
  if (typeof raw === "string") return raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  return [];
}

const MONDO_IRI_PREFIX = "http://purl.obolibrary.org/obo/MONDO_";

/** Normalize MONDO CURIE or IRI to full IRI for SPARQL/APIs. */
function normalizeMondoToIri(value: string): string {
  const s = value.trim().replace(/[<>]/g, "");
  if (!s) return "";
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  const numeric = s.replace(/^MONDO[:_]/i, "").replace(/^MONDO_?/i, "").trim();
  if (!numeric || !/^\d+$/.test(numeric)) return s;
  return `${MONDO_IRI_PREFIX}${numeric}`;
}
