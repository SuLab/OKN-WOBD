/**
 * UBERON anatomy/tissue search for autocomplete.
 * - searchUBERONViaUbergraph: FRINK Ubergraph SPARQL (rdfs:label + oboInOwl:hasExactSynonym)
 * - searchUBERONViaOLS: OLS API (ranked, fast)
 */

import { executeSPARQL } from "@/lib/sparql/executor";
import { groundTermToUBERON } from "@/lib/ontology/ols-client";

const UBERGRAPH_ENDPOINT =
  process.env.NEXT_PUBLIC_UBERGRAPH_SPARQL_URL ||
  "https://frink.apps.renci.org/ubergraph/sparql";

const UBERON_IRI_PREFIX = "http://purl.obolibrary.org/obo/UBERON_";

export interface UBERONSearchResult {
  iri: string;
  shortForm: string;
  uberonId: string;
  label: string;
  matchedSynonym?: string;
}

/**
 * Sanitize search term for safe use inside a SPARQL string literal.
 * Only allows letters, numbers, space, hyphen, underscore, apostrophe (no quotes or backslashes).
 */
function sanitizeSearchTerm(term: string): string {
  const trimmed = term.trim();
  if (!trimmed) return "";
  return trimmed.replace(/[^a-zA-Z0-9 _\-']/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * Search UBERON in Ubergraph by rdfs:label and oboInOwl:hasExactSynonym.
 * Returns distinct classes with label and optional matched synonym.
 */
export async function searchUBERONViaUbergraph(
  searchTerm: string,
  limit: number = 20
): Promise<UBERONSearchResult[]> {
  const safe = sanitizeSearchTerm(searchTerm);
  if (!safe || safe.length < 2) {
    return [];
  }

  const query = `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>

SELECT DISTINCT ?iri ?label ?syn
WHERE {
  {
    ?iri rdfs:label ?label .
    FILTER(STRSTARTS(STR(?iri), "${UBERON_IRI_PREFIX}"))
    FILTER(CONTAINS(LCASE(?label), LCASE("${safe}")))
    BIND(?label AS ?syn)
  } UNION {
    ?iri oboInOwl:hasExactSynonym ?syn .
    ?iri rdfs:label ?label .
    FILTER(STRSTARTS(STR(?iri), "${UBERON_IRI_PREFIX}"))
    FILTER(CONTAINS(LCASE(?syn), LCASE("${safe}")))
  }
}
ORDER BY ?label
LIMIT ${Math.min(Math.max(limit, 1), 50)}
`.trim();

  try {
    const result = await executeSPARQL(query, UBERGRAPH_ENDPOINT, {
      timeout_s: 25,
      max_rows: limit,
    });

    if (result.error) {
      console.warn("[UBERON/Ubergraph] Search failed:", result.error);
      return [];
    }

    const bindings = result.result.results?.bindings ?? [];
    const seen = new Set<string>();
    const out: UBERONSearchResult[] = [];

    for (const b of bindings) {
      const iri = b.iri?.value;
      if (!iri || seen.has(iri)) continue;
      seen.add(iri);
      const shortForm = iri.replace(UBERON_IRI_PREFIX, "UBERON_");
      const match = shortForm.match(/UBERON_(\d+)/);
      const uberonId = match ? match[1] : "";
      const label = b.label?.value ?? shortForm;
      const syn = b.syn?.value;
      out.push({
        iri,
        shortForm: shortForm.replace("UBERON_", "UBERON:"),
        uberonId,
        label,
        matchedSynonym: syn && syn !== label ? syn : undefined,
      });
    }

    return out;
  } catch (err) {
    console.error("[UBERON/Ubergraph] Error:", err);
    return [];
  }
}

/**
 * Search UBERON via OLS API.
 * Faster than Ubergraph and returns ranked results (e.g. "heat" → "heart" first).
 */
export async function searchUBERONViaOLS(
  searchTerm: string,
  limit: number = 20
): Promise<UBERONSearchResult[]> {
  const safe = searchTerm.trim().replace(/[^a-zA-Z0-9 _\-']/g, " ").replace(/\s+/g, " ").trim();
  if (!safe || safe.length < 2) return [];

  const ranked = await groundTermToUBERON(safe, Math.min(limit, 50));
  return ranked.map((r) => {
    const shortForm = r.obo_id ?? (r.short_form || "").replace("UBERON_", "UBERON:");
    const iri = r.iri ?? `http://purl.obolibrary.org/obo/UBERON_${r.uberonId ?? ""}`;
    return {
      iri,
      shortForm,
      uberonId: r.uberonId ?? "",
      label: r.label ?? shortForm,
      matchedSynonym: r.matchedText && r.matchedText !== r.label ? r.matchedText : undefined,
    };
  });
}
