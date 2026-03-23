/**
 * MONDO (disease ontology) search via OLS for autocomplete.
 * Used for disease / health_conditions in gene expression templates.
 */

import { searchOLS, rankMONDOCTerms, type OLSSearchResult } from "@/lib/ontology/ols-client";

export interface MONDOSearchResult {
  iri: string;
  shortForm: string;
  label: string;
  matchedSynonym?: string;
}

function isMONDOTerm(result: OLSSearchResult): boolean {
  if (result.obo_id && result.obo_id.startsWith("MONDO:")) return true;
  if (result.ontology_prefix === "MONDO") return true;
  if (result.ontology_name === "mondo") return true;
  if (result.iri && result.iri.includes("/MONDO_")) return true;
  if (result.short_form && result.short_form.startsWith("MONDO_")) return true;
  return false;
}

/**
 * Search MONDO via OLS API.
 * Returns ranked disease terms for autocomplete (fast, OLS-based).
 */
export async function searchMONDOViaOLS(
  searchTerm: string,
  limit: number = 20
): Promise<MONDOSearchResult[]> {
  const safe = searchTerm.trim().replace(/[^a-zA-Z0-9 _\-']/g, " ").replace(/\s+/g, " ").trim();
  if (!safe || safe.length < 2) return [];

  const results = await searchOLS(safe, "mondo", Math.min(limit, 50));
  const mondoResults = results.filter(isMONDOTerm);
  if (mondoResults.length === 0) return [];

  const ranked = rankMONDOCTerms(mondoResults, safe);
  const filtered = ranked.filter((r) => r.matchScore > 0).slice(0, limit);

  return filtered.map((r) => {
    const oboId = r.obo_id ?? r.short_form?.replace(/_/g, ":") ?? "";
    const shortForm = oboId || (r.short_form ? r.short_form.replace(/_/g, ":") : "");
    const iri = r.iri ?? (shortForm ? `http://purl.obolibrary.org/obo/${shortForm.replace(":", "_")}` : "");
    return {
      iri,
      shortForm,
      label: r.label ?? shortForm,
      matchedSynonym: r.matchedText && r.matchedText !== r.label ? r.matchedText : undefined,
    };
  });
}
