/**
 * Resolve MONDO disease IRIs to EFO (Experimental Factor Ontology) IRIs for use with
 * SPOKE-GeneLab / GXA (Study --studies--> Disease uses EFO).
 * Pipeline provides MONDO from Wikidata; SPOKE-GeneLab uses EFO.
 *
 * Two strategies:
 * 1. Ubergraph: MONDO terms may have oboInOwl:hasDbXref with literal value "EFO:0000275".
 * 2. OLS: Fetch MONDO term by IRI from OLS and read xrefs from the term response.
 */

import { executeSPARQL } from "@/lib/sparql/executor";

const OBO_IN_OWL = "http://www.geneontology.org/formats/oboInOwl#";
const EFO_PREFIX = "http://www.ebi.ac.uk/efo/EFO_";

/** Convert EFO CURIE (e.g. "EFO:0000275") to EFO IRI. */
export function efoCurieToIri(curie: string): string {
  const s = curie.trim();
  const match = s.match(/^EFO:(\d+)$/i);
  if (match) return `${EFO_PREFIX}${match[1]}`;
  if (s.startsWith(EFO_PREFIX)) return s;
  return s.replace(/^EFO_/, EFO_PREFIX).replace(/^EFO:/i, EFO_PREFIX);
}

/**
 * Build SPARQL query to get MONDO -> EFO xrefs from Ubergraph.
 * MONDO terms may have oboInOwl:hasDbXref with literal value "EFO:xxxx".
 * No FROM clause: FRINK's ubergraph endpoint serves MONDO from the default graph.
 */
export function buildMONDOToEFOXrefQuery(mondoIRIs: string[]): string | null {
  if (mondoIRIs.length === 0) return null;
  const safe = mondoIRIs
    .map((iri) => iri.trim())
    .filter(Boolean)
    .slice(0, 100)
    .map((iri) => `<${iri.replace(/[<>]/g, "")}>`)
    .join(" ");
  return `PREFIX oboInOwl: <${OBO_IN_OWL}>

SELECT ?mondo ?xref
WHERE {
  VALUES ?mondo { ${safe} }
  ?mondo oboInOwl:hasDbXref ?xref .
  FILTER(REGEX(STR(?xref), "^EFO:[0-9]+$", "i"))
}`;
}

/**
 * Resolve MONDO IRIs to EFO IRIs using Ubergraph (hasDbXref).
 * Returns a map: MONDO IRI -> list of EFO IRIs (may be empty for some MONDOs).
 */
export async function getEFOFromUbergraph(
  mondoIRIs: string[],
  endpoint: string
): Promise<Map<string, string[]>> {
  const out = new Map<string, string[]>();
  mondoIRIs.forEach((iri) => out.set(iri, []));
  const query = buildMONDOToEFOXrefQuery(mondoIRIs);
  if (!query) return out;
  try {
    const res = await executeSPARQL(query, endpoint, { timeout_s: 25 });
    const bindings = res.result?.results?.bindings ?? [];
    for (const b of bindings as Array<Record<string, { value?: string }>>) {
      const mondo = b.mondo?.value;
      const xref = b.xref?.value;
      if (mondo && xref) {
        const list = out.get(mondo) ?? [];
        const efoIri = efoCurieToIri(xref);
        if (!list.includes(efoIri)) list.push(efoIri);
        out.set(mondo, list);
      }
    }
  } catch {
    // non-fatal
  }
  return out;
}

const OLS_TERM_BASE = "https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms";

/** Extract EFO CURIEs from OLS term JSON (annotation, oboXref, etc.). */
function extractEfoFromOLSTerm(term: Record<string, unknown>): string[] {
  const efoCuries: string[] = [];
  const annotations = term.annotation as Record<string, unknown>[] | undefined;
  if (annotations && Array.isArray(annotations)) {
    for (const a of annotations) {
      const pred = (a as Record<string, unknown>).predicate as string | undefined;
      const val = (a as Record<string, unknown>).value as string | undefined;
      if (pred?.includes("hasDbXref") && typeof val === "string" && /^EFO:\d+$/i.test(val.trim()))
        efoCuries.push(val.trim());
    }
  }
  const oboXref = term.oboXref as string[] | string | undefined;
  if (Array.isArray(oboXref)) {
    for (const x of oboXref) {
      if (typeof x === "string" && /^EFO:\d+$/i.test(x.trim())) efoCuries.push(x.trim());
    }
  } else if (typeof oboXref === "string" && /^EFO:\d+$/i.test(oboXref.trim())) {
    efoCuries.push(oboXref.trim());
  }
  return [...new Set(efoCuries)];
}

/**
 * Fetch one MONDO term from OLS by IRI (or by term id) and extract EFO xrefs.
 */
async function fetchOLSTermEfoXrefs(mondoIri: string): Promise<string[]> {
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
      const efoCuries = extractEfoFromOLSTerm(term as Record<string, unknown>);
      if (efoCuries.length > 0) return efoCuries.map((c) => efoCurieToIri(c));
    } catch {
      // try next URL
    }
  }
  return [];
}

/** Get EFO IRIs from OLS for the given MONDO IRIs (batch with small concurrency). */
export async function getEFOFromOLS(mondoIRIs: string[]): Promise<Map<string, string[]>> {
  const out = new Map<string, string[]>();
  const limit = 20;
  const batch = mondoIRIs.slice(0, limit);
  await Promise.all(
    batch.map(async (iri) => {
      const efoIris = await fetchOLSTermEfoXrefs(iri);
      out.set(iri, efoIris);
    })
  );
  return out;
}

export interface ResolveMondoToEfoOptions {
  ubergraphEndpoint?: string;
  useOLSFallback?: boolean;
}

/**
 * Resolve MONDO IRIs to EFO IRIs. Tries Ubergraph first; for MONDOs with no EFO,
 * optionally falls back to OLS. Returns the combined list of EFO IRIs.
 */
export async function resolveMondoToEfo(
  mondoIRIs: string[],
  options: ResolveMondoToEfoOptions = {}
): Promise<{ efoIris: string[]; mondoToEfo: Map<string, string[]> }> {
  const { ubergraphEndpoint, useOLSFallback = true } = options;
  const mondoToEfo = new Map<string, string[]>();

  if (ubergraphEndpoint) {
    const fromUbergraph = await getEFOFromUbergraph(mondoIRIs, ubergraphEndpoint);
    fromUbergraph.forEach((efos, mondo) => {
      if (efos.length > 0) mondoToEfo.set(mondo, efos);
    });
  }

  const missing = useOLSFallback ? mondoIRIs.filter((iri) => !mondoToEfo.get(iri)?.length) : [];
  if (missing.length > 0) {
    const fromOLS = await getEFOFromOLS(missing);
    fromOLS.forEach((efos, mondo) => {
      if (efos.length > 0) mondoToEfo.set(mondo, efos);
    });
  }

  const efoIris = [...new Set(Array.from(mondoToEfo.values()).flat())];
  return { efoIris, mondoToEfo };
}
