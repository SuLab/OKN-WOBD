/**
 * Resolve MONDO disease IRIs to DOID (Disease Ontology) IRIs for use with SPOKE-OKN.
 * SPOKE-OKN uses DOID; our pipeline provides MONDO from Wikidata.
 *
 * Two strategies:
 * 1. Ubergraph: MONDO ontology in Ubergraph has oboInOwl:hasDbXref literals (e.g. "DOID:0050589").
 * 2. OLS: Fetch MONDO term by IRI from OLS and read xrefs from the term response.
 */

import { executeSPARQL } from "@/lib/sparql/executor";

const OBO_IN_OWL = "http://www.geneontology.org/formats/oboInOwl#";
const DOID_PREFIX = "http://purl.obolibrary.org/obo/DOID_";

/** Convert DOID CURIE (e.g. "DOID:0050589") to DOID IRI. */
export function doidCurieToIri(curie: string): string {
  const s = curie.trim();
  const match = s.match(/^DOID:(\d+)$/i);
  if (match) return `${DOID_PREFIX}${match[1]}`;
  if (s.startsWith(DOID_PREFIX)) return s;
  return s.replace(/^DOID_/, DOID_PREFIX).replace(/^DOID:/i, DOID_PREFIX);
}

/**
 * Build SPARQL query to get MONDO -> DOID xrefs from Ubergraph.
 * MONDO terms may have oboInOwl:hasDbXref with literal value "DOID:xxxx".
 */
export function buildMONDOToDOIDXrefQuery(mondoIRIs: string[]): string | null {
  if (mondoIRIs.length === 0) return null;
  const safe = mondoIRIs
    .map((iri) => iri.trim())
    .filter(Boolean)
    .slice(0, 100)
    .map((iri) => `<${iri.replace(/[<>]/g, "")}>`)
    .join(" ");
  return `PREFIX oboInOwl: <${OBO_IN_OWL}>

SELECT ?mondo ?xref
FROM <https://purl.org/okn/frink/kg/ubergraph>
WHERE {
  VALUES ?mondo { ${safe} }
  ?mondo oboInOwl:hasDbXref ?xref .
  FILTER(REGEX(STR(?xref), "^DOID:[0-9]+$", "i"))
}`;
}

/**
 * Resolve MONDO IRIs to DOID IRIs using Ubergraph (hasDbXref).
 * Returns a map: MONDO IRI -> list of DOID IRIs (may be empty for some MONDOs).
 */
export async function getDOIDFromUbergraph(
  mondoIRIs: string[],
  endpoint: string
): Promise<Map<string, string[]>> {
  const out = new Map<string, string[]>();
  mondoIRIs.forEach((iri) => out.set(iri, []));
  const query = buildMONDOToDOIDXrefQuery(mondoIRIs);
  if (!query) return out;
  try {
    const res = await executeSPARQL(query, endpoint, { timeout_s: 25 });
    const bindings = res.result?.results?.bindings ?? [];
    for (const b of bindings as Array<Record<string, { value?: string }>>) {
      const mondo = b.mondo?.value;
      const xref = b.xref?.value;
      if (mondo && xref) {
        const list = out.get(mondo) ?? [];
        const doidIri = doidCurieToIri(xref);
        if (!list.includes(doidIri)) list.push(doidIri);
        out.set(mondo, list);
      }
    }
  } catch {
    // non-fatal
  }
  return out;
}

const OLS_TERM_BASE = "https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms";

/** Extract DOID CURIEs from OLS term JSON (annotation, oboXref, etc.). */
function extractDoidFromOLSTerm(term: Record<string, unknown>): string[] {
  const doidCuries: string[] = [];
  const annotations = term.annotation as Record<string, unknown>[] | undefined;
  if (annotations && Array.isArray(annotations)) {
    for (const a of annotations) {
      const pred = (a as Record<string, unknown>).predicate as string | undefined;
      const val = (a as Record<string, unknown>).value as string | undefined;
      if (pred?.includes("hasDbXref") && typeof val === "string" && /^DOID:\d+$/i.test(val.trim()))
        doidCuries.push(val.trim());
    }
  }
  const oboXref = term.oboXref as string[] | string | undefined;
  if (Array.isArray(oboXref)) {
    for (const x of oboXref) {
      if (typeof x === "string" && /^DOID:\d+$/i.test(x.trim())) doidCuries.push(x.trim());
    }
  } else if (typeof oboXref === "string" && /^DOID:\d+$/i.test(oboXref.trim())) {
    doidCuries.push(oboXref.trim());
  }
  return [...new Set(doidCuries)];
}

/**
 * Fetch one MONDO term from OLS by IRI (or by term id) and extract DOID xrefs.
 * OLS4: term by IRI = GET .../terms?iri=... or by id = GET .../terms/MONDO_0005015
 */
async function fetchOLSTermXrefs(mondoIri: string): Promise<string[]> {
  const termId = mondoIri.replace(/^https?:\/\/purl\.obolibrary\.org\/obo\/MONDO_/, "MONDO_");
  const urls = [
    `${OLS_TERM_BASE}/${encodeURIComponent(termId)}`,
    `${OLS_TERM_BASE}?iri=${encodeURIComponent(mondoIri)}`,
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) continue;
      const data = (await res.json()) as Record<string, unknown>;
      const term = (data._embedded as Record<string, unknown>)?.term ?? data;
      const doidCuries = extractDoidFromOLSTerm(term as Record<string, unknown>);
      if (doidCuries.length > 0) return doidCuries.map((c) => doidCurieToIri(c));
    } catch {
      // try next URL
    }
  }
  return [];
}

/** Get DOID IRIs from OLS for the given MONDO IRIs (batch with small concurrency). */
export async function getDOIDFromOLS(mondoIRIs: string[]): Promise<Map<string, string[]>> {
  const out = new Map<string, string[]>();
  const limit = 20; // avoid hammering OLS
  const batch = mondoIRIs.slice(0, limit);
  await Promise.all(
    batch.map(async (iri) => {
      const doidIris = await fetchOLSTermXrefs(iri);
      out.set(iri, doidIris);
    })
  );
  return out;
}

export interface ResolveMondoToDoidOptions {
  ubergraphEndpoint?: string;
  useOLSFallback?: boolean;
}

/**
 * Resolve MONDO IRIs to DOID IRIs. Tries Ubergraph first; for MONDOs with no DOID,
 * optionally falls back to OLS. Returns the combined list of DOID IRIs (and optionally
 * keeps MONDO IRIs that had no mapping for SPOKE-OKN if it supports both).
 */
export async function resolveMondoToDoid(
  mondoIRIs: string[],
  options: ResolveMondoToDoidOptions = {}
): Promise<{ doidIris: string[]; mondoToDoid: Map<string, string[]> }> {
  const { ubergraphEndpoint, useOLSFallback = true } = options;
  const mondoToDoid = new Map<string, string[]>();

  if (ubergraphEndpoint) {
    const fromUbergraph = await getDOIDFromUbergraph(mondoIRIs, ubergraphEndpoint);
    fromUbergraph.forEach((doids, mondo) => {
      if (doids.length > 0) mondoToDoid.set(mondo, doids);
    });
  }

  const missing = useOLSFallback ? mondoIRIs.filter((iri) => !mondoToDoid.get(iri)?.length) : [];
  if (missing.length > 0) {
    const fromOLS = await getDOIDFromOLS(missing);
    fromOLS.forEach((doids, mondo) => {
      if (doids.length > 0) mondoToDoid.set(mondo, doids);
    });
  }

  const doidIris = [...new Set(Array.from(mondoToDoid.values()).flat())];
  return { doidIris, mondoToDoid };
}
