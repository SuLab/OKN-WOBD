/**
 * MONDO disease search via OLS for template autocomplete (NDE health condition facet).
 */

import { mondoDigitsToOboId, mondoDigitsToOboIri } from "@/lib/ontology/mondo-iri";
import { groundTermToMONDO } from "@/lib/ontology/ols-client";

export interface MONDOsearchResult {
  iri: string;
  shortForm: string;
  /** e.g. MONDO:0005015 */
  oboId: string;
  label: string;
  matchedSynonym?: string;
}

/** Normalize user input into an OLS query (label text, MONDO CURIE, bare numeric id, or MONDO IRI). */
function normalizeMONDOQuery(trimmed: string): string | null {
  if (!trimmed) return null;
  const curie = trimmed.match(/^MONDO[:_\s]+0*(\d+)$/i);
  if (curie) return `MONDO:${curie[1]}`;
  const fromIri = trimmed.match(
    /^https?:\/\/purl\.obolibrary\.org\/obo\/MONDO_0*(\d+)$/i
  );
  if (fromIri) return `MONDO:${fromIri[1]}`;
  if (/^\d{4,10}$/.test(trimmed)) return `MONDO:${trimmed.replace(/^0+/, "") || "0"}`;
  const safe = trimmed.replace(/[^a-zA-Z0-9 _\-']/g, " ").replace(/\s+/g, " ").trim();
  if (safe.length < 2) return null;
  return safe;
}

/**
 * Search MONDO via OLS for autocomplete.
 * `humanOnly` is false so infectious / veterinary terms still appear (NDE scope).
 */
export async function searchMONDOViaOLS(
  searchTerm: string,
  limit: number = 20
): Promise<MONDOsearchResult[]> {
  const query = normalizeMONDOQuery(searchTerm.trim());
  if (!query) return [];

  const ranked = await groundTermToMONDO(query, Math.min(limit, 50), false);
  const isCurieQuery = /^MONDO:\d+$/i.test(query);
  const toComparableId = (obo_id?: string, short_form?: string) =>
    (obo_id ?? short_form ?? "").replace(/\s/g, ":").replace(/_/g, ":").toLowerCase();
  const ordered = isCurieQuery
    ? [...ranked].sort((a, b) => {
        const q = query.toLowerCase();
        const aId = toComparableId(a.obo_id, a.short_form);
        const bId = toComparableId(b.obo_id, b.short_form);
        if (aId === q && bId !== q) return -1;
        if (bId === q && aId !== q) return 1;
        return 0;
      })
    : ranked;

  return ordered
    .map((r): MONDOsearchResult | null => {
      const idSource = `${r.obo_id ?? ""} ${r.short_form ?? ""} ${r.iri ?? ""}`;
      // Capture full digit run (keep leading zeros from OLS) so we don't turn 0005015 → 5015.
      const oboMatch = idSource.match(/MONDO[:\s_/]+(\d+)/i);
      const digits = oboMatch ? oboMatch[1] : "";
      if (!digits) return null;
      const oboId = mondoDigitsToOboId(digits);
      // Colon CURIE for UI (MONDO:0005015); OLS short_form is typically MONDO_0005015.
      const shortForm = oboId;
      const iri = mondoDigitsToOboIri(digits);
      return {
        iri,
        shortForm,
        oboId,
        label: r.label ?? oboId,
        matchedSynonym:
          r.matchedText && r.matchedText !== r.label ? r.matchedText : undefined,
      };
    })
    .filter((x): x is MONDOsearchResult => x !== null);
}
