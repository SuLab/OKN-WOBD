/**
 * MONDO OBO IRIs use a zero-padded numeric local id (typically 7 digits), e.g. MONDO_0005015 — not MONDO_5015.
 */

/** Strip leading zeros then pad to 7 digits for classic MONDO OBO ids; longer ids kept as-is. */
export function formatMondoLocalId(digits: string): string {
  const stripped = digits.replace(/^0+/, "") || "0";
  return stripped.length < 7 ? stripped.padStart(7, "0") : stripped;
}

export function mondoDigitsToOboIri(digits: string): string {
  const local = formatMondoLocalId(digits);
  return `http://purl.obolibrary.org/obo/MONDO_${local}`;
}

export function mondoDigitsToOboId(digits: string): string {
  return `MONDO:${formatMondoLocalId(digits)}`;
}
