/**
 * Recognize Ensembl gene stable IDs (e.g. ENSG00000157764, ENSMUSG00000034994).
 * Uses the usual pattern: ENS + optional species/product prefix + G + numeric suffix.
 */
export function isEnsemblGeneStableId(value: string): boolean {
  const s = value.trim();
  return /^ENS[A-Z0-9]*G[0-9]+$/i.test(s);
}
