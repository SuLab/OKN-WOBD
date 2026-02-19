/**
 * Experimental Factor Ontology (EFO) search via OLS for autocomplete.
 * Used for factor terms in gene expression contrast labels.
 */

import { searchOLS, rankMONDOCTerms, type OLSSearchResult } from "@/lib/ontology/ols-client";

export interface EFOSearchResult {
  iri: string;
  shortForm: string;
  efoId: string;
  label: string;
  matchedSynonym?: string;
}

function isEFOTerm(result: OLSSearchResult): boolean {
  if (result.obo_id && result.obo_id.startsWith("EFO:")) return true;
  if (result.ontology_prefix === "EFO") return true;
  if (result.ontology_name === "efo") return true;
  if (result.iri && (result.iri.includes("/EFO_") || result.iri.includes("/efo/"))) return true;
  if (result.short_form && result.short_form.startsWith("EFO_")) return true;
  return false;
}

/**
 * Search EFO via OLS API.
 * Returns ranked experimental factor terms for autocomplete.
 */
export async function searchEFOViaOLS(
  searchTerm: string,
  limit: number = 20
): Promise<EFOSearchResult[]> {
  const safe = searchTerm.trim().replace(/[^a-zA-Z0-9 _\-']/g, " ").replace(/\s+/g, " ").trim();
  if (!safe || safe.length < 2) return [];

  const results = await searchOLS(safe, "efo", Math.min(limit, 50));
  const efoResults = results.filter(isEFOTerm);
  if (efoResults.length === 0) return [];

  const ranked = rankMONDOCTerms(efoResults, safe);
  const filtered = ranked.filter((r) => r.matchScore > 0).slice(0, limit);

  return filtered.map((r) => {
    const oboId = r.obo_id ?? r.short_form ?? "";
    const match = oboId.match(/EFO[:\s_]*(\d+)/i);
    const efoId = match ? match[1] : "";
    const shortForm = oboId || `EFO:${efoId}`;
    const iri = r.iri ?? `http://www.ebi.ac.uk/efo/EFO_${efoId}`;
    return {
      iri,
      shortForm,
      efoId,
      label: r.label ?? shortForm,
      matchedSynonym: r.matchedText && r.matchedText !== r.label ? r.matchedText : undefined,
    };
  });
}
