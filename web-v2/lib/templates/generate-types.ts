/**
 * Rich return type for template generators (beyond a plain SPARQL string).
 * Used by dataset_search when MONDO expansion supplies extra UI metadata.
 */
export interface TemplateGenerateResult {
  query: string;
  /** Preferred disease labels from OLS for expanded MONDO subclasses (result highlighting). */
  mondoExpansionHighlightLabels?: string[];
}
