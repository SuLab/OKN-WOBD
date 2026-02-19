/**
 * NCBITaxon / organism search via OLS for autocomplete.
 * Returns ranked results (e.g. "mouse" → Mus musculus first).
 */

import { groundTermToNCBITaxon } from "@/lib/ontology/ols-client";

export interface NCBITaxonSearchResult {
  iri: string;
  shortForm: string;
  taxonId: string;
  label: string;
  matchedSynonym?: string;
}

/** Normalize CURIE to NCBITaxon:ID for OLS (e.g. NCBITaxon_10090 → NCBITaxon:10090). */
function normalizeNCBITaxonCurie(s: string): string | null {
  const m = s.match(/^NCBITaxon[:\s_]+(\d+)$/i);
  return m ? `NCBITaxon:${m[1]}` : null;
}

/**
 * Search NCBITaxon via OLS API.
 * Returns ranked organism results for autocomplete.
 * Supports: text (e.g. "mouse"), bare ID (e.g. "10090"), and CURIE (e.g. "NCBITaxon:10090" or "NCBITaxon_10090").
 */
export async function searchNCBITaxonViaOLS(
  searchTerm: string,
  limit: number = 20
): Promise<NCBITaxonSearchResult[]> {
  const trimmed = searchTerm.trim();
  if (!trimmed) return [];

  let query: string;
  const curie = normalizeNCBITaxonCurie(trimmed);
  if (curie) {
    query = curie;
  } else if (/^\d+$/.test(trimmed)) {
    query = `NCBITaxon:${trimmed}`;
  } else {
    const safe = trimmed.replace(/[^a-zA-Z0-9 _\-']/g, " ").replace(/\s+/g, " ").trim();
    if (safe.length < 2) return [];
    query = safe;
  }

  const ranked = await groundTermToNCBITaxon(query, Math.min(limit, 50));

  // When query is by identifier (CURIE), put exact match first so e.g. "10090" or "NCBITaxon:10090" shows Mus musculus at top
  const isCurieQuery = /^NCBITaxon:\d+$/i.test(query);
  const toComparableId = (r: { obo_id?: string; short_form?: string }) =>
    (r.obo_id ?? r.short_form ?? "").replace(/\s/g, ":").replace(/_/g, ":").toLowerCase();
  const ordered = isCurieQuery
    ? [...ranked].sort((a, b) => {
        const q = query.toLowerCase();
        const aId = toComparableId(a);
        const bId = toComparableId(b);
        if (aId === q && bId !== q) return -1;
        if (bId === q && aId !== q) return 1;
        return 0;
      })
    : ranked;

  return ordered.map((r) => {
    const oboId = r.obo_id ?? r.short_form ?? "";
    const match = oboId.match(/NCBITaxon[:\s]*(\d+)/i);
    const taxonId = match ? match[1] : "";
    const shortForm = oboId || `NCBITaxon:${taxonId}`;
    const iri = r.iri ?? `http://purl.obolibrary.org/obo/NCBITaxon_${taxonId}`;
    return {
      iri,
      shortForm,
      taxonId,
      label: r.label ?? shortForm,
      matchedSynonym: r.matchedText && r.matchedText !== r.label ? r.matchedText : undefined,
    };
  });
}
