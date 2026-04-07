/**
 * Detect GEO / GSE / E-GEOD mentions in NDE dataset SPARQL rows (client-safe, no SPARQL).
 * Used to filter "gene expression" datasets without a slow GXA federated round-trip.
 */

/** String value from a SPARQL JSON binding cell. */
export function ndeBindingString(raw: { type: string; value: string } | string | undefined): string {
  if (raw == null) return "";
  if (typeof raw === "object" && "value" in raw) return String((raw as { value: string }).value ?? "");
  return String(raw);
}

function getBindingField(b: Record<string, unknown>, key: string): string {
  const raw = b[key] ?? b[key.charAt(0).toUpperCase() + key.slice(1)];
  return ndeBindingString(raw as { type: string; value: string } | string | undefined);
}

/** Convert a single token to E-GEOD id when it is GSE… or E-GEOD-… */
export function identifierToEGeod(identifier: string): string | null {
  if (!identifier || typeof identifier !== "string") return null;
  const s = identifier.trim();
  const gseMatch = s.match(/GSE(\d+)/i);
  if (gseMatch) return `E-GEOD-${gseMatch[1]}`;
  const eGeodMatch = s.match(/E-GEOD-(\d+)/i);
  return eGeodMatch ? `E-GEOD-${eGeodMatch[1]}` : null;
}

/** All E-GEOD experiment ids mentioned in a string (GSE123, E-GEOD-123, GEO URLs, etc.). */
export function extractEGeodIdsFromText(text: string): string[] {
  if (!text || typeof text !== "string") return [];
  const ids = new Set<string>();
  const gseMatches = text.matchAll(/GSE(\d+)/gi);
  for (const m of gseMatches) ids.add(`E-GEOD-${m[1]}`);
  const eGeodMatches = text.matchAll(/E-GEOD-(\d+)/gi);
  for (const m of eGeodMatches) ids.add(`E-GEOD-${m[1]}`);
  return [...ids];
}

/**
 * E-GEOD candidates per row from identifier (may be GROUP_CONCAT), name, description, url/sameAs lists.
 */
export function eGeodCandidatesPerNdeBinding(bindings: Array<Record<string, unknown>>): Set<string>[] {
  return bindings.map((raw) => {
    const idVal = getBindingField(raw, "identifier");
    const nameVal = getBindingField(raw, "name");
    const descVal = getBindingField(raw, "description");
    const urlsVal = getBindingField(raw, "urls");
    const sameAsVal = getBindingField(raw, "sameAsList");
    const owlSameAsVal = getBindingField(raw, "owlSameAsList");
    const ids = new Set<string>();
    for (const e of extractEGeodIdsFromText(idVal)) ids.add(e);
    for (const e of extractEGeodIdsFromText(nameVal)) ids.add(e);
    for (const e of extractEGeodIdsFromText(descVal)) ids.add(e);
    for (const e of extractEGeodIdsFromText(urlsVal)) ids.add(e);
    for (const e of extractEGeodIdsFromText(sameAsVal)) ids.add(e);
    for (const e of extractEGeodIdsFromText(owlSameAsVal)) ids.add(e);
    return ids;
  });
}

/** True if NDE metadata suggests a GEO series / expression-style accession (GSE or E-GEOD). */
export function ndeBindingHasGeoOrGseEvidence(binding: Record<string, unknown>): boolean {
  const set = eGeodCandidatesPerNdeBinding([binding])[0];
  return set.size > 0;
}
