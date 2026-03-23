/**
 * MONDO descendant expansion via Ubergraph.
 * Given MONDO IRIs, returns the union of those IRIs and all MONDO terms
 * that are rdfs:subClassOf* (transitive) any of them.
 */

import { executeSPARQL } from "@/lib/sparql/executor";

const MONDO_URI_PREFIX = "http://purl.obolibrary.org/obo/MONDO_";

export interface ExpandMondoToDescendantsOptions {
  maxTerms?: number;
  endpoint?: string;
}

/**
 * Build SPARQL query to get all MONDO IRIs that are subClassOf* (descendants of) the given parents.
 * Includes the parent IRIs themselves in the result.
 */
export function buildMondoDescendantsQuery(
  mondoIRIs: string[],
  maxTerms: number = 200
): string {
  if (mondoIRIs.length === 0) {
    throw new Error("At least one MONDO IRI required for descendant expansion");
  }
  const safe = mondoIRIs
    .map((iri) => iri.trim())
    .filter(Boolean)
    .slice(0, 20)
    .map((iri) => `<${iri.replace(/[<>]/g, "")}>`)
    .join("\n    ");
  const limit = Math.min(maxTerms, 500);
  return `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?subclass
WHERE {
  VALUES ?parent {
    ${safe}
  }
  ?subclass rdfs:subClassOf* ?parent .
  ?subclass a owl:Class .
  FILTER(STRSTARTS(STR(?subclass), "${MONDO_URI_PREFIX}"))
}
LIMIT ${limit}`;
}

/**
 * Expand a list of MONDO IRIs to include all descendants (subClassOf*).
 * Returns the union of the input IRIs and all MONDO IRIs that are transitive subclasses.
 */
export async function expandMondoToDescendants(
  mondoIRIs: string[],
  options: ExpandMondoToDescendantsOptions = {}
): Promise<string[]> {
  const { maxTerms = 200, endpoint } = options;
  if (mondoIRIs.length === 0) return [];

  const query = buildMondoDescendantsQuery(mondoIRIs, maxTerms);
  const effectiveEndpoint =
    endpoint || "https://frink.apps.renci.org/ubergraph/sparql";

  const { result, error } = await executeSPARQL(query, effectiveEndpoint, {
    timeout_s: 25,
  });

  if (error) {
    throw new Error(`MONDO descendant expansion failed: ${error}`);
  }

  const bindings = (result?.results?.bindings ?? []) as Array<{
    subclass?: { value?: string };
  }>;
  const seen = new Set<string>();
  const out: string[] = [];

  // Include input IRIs first (normalize to full IRI)
  for (const iri of mondoIRIs) {
    const raw = iri.trim().replace(/[<>]/g, "");
    if (!raw) continue;
    const full =
      raw.startsWith("http") ? raw : `${MONDO_URI_PREFIX}${raw.replace(/^MONDO_?/, "")}`;
    if (full.startsWith(MONDO_URI_PREFIX) && !seen.has(full)) {
      seen.add(full);
      out.push(full);
    }
  }

  for (const row of bindings) {
    const iri = row.subclass?.value;
    if (iri && iri.startsWith(MONDO_URI_PREFIX) && !seen.has(iri)) {
      seen.add(iri);
      out.push(iri);
    }
  }

  return out;
}
