import type { Intent } from "@/types";
import type { ContextPack } from "@/lib/context-packs/types";

// Phase 3: keep classifier deterministic and cheap.
// Phase 4 can add LLM-based classification via /api/tools/llm/complete.

export interface ClassificationResult {
  intent: Intent;
}

export function classifyIntentDeterministic(
  text: string,
  pack: ContextPack,
  baseIntent: Intent
): ClassificationResult {
  const lowered = text.toLowerCase();
  let task = baseIntent.task;
  let confidence = 0.7;
  const slots = { ...(baseIntent.slots || {}) };
  let notes = baseIntent.notes || "";

  // Simple pattern-based task selection
  // Phase 5: GXA task routing – check more specific patterns first
  if (lowered.startsWith("/entity")) {
    task = "entity_lookup";
    confidence = 0.9;
    notes += " | Classified as entity_lookup via /entity command";
  } else if (
    // genes_in_experiment: "genes in E-GEOD-76", "DE genes in experiment X"
    (lowered.includes("genes in") || lowered.includes("genes for") || lowered.includes("genes from")) &&
    /e-geod-\d+/i.test(text)
  ) {
    task = "gene_expression_genes_in_experiment";
    confidence = 0.8;
    notes += " | Classified as gene_expression_genes_in_experiment (genes in experiment)";
  } else if (
    // genes_in_experiment: "differentially expressed genes in E-GEOD-76" or "genes are DE in E-GEOD-76"
    ((lowered.includes("differential") || lowered.includes("differentially")) ||
      (/\bde\b/i.test(text) && lowered.includes("genes") && lowered.includes("in"))) &&
    lowered.includes("genes") &&
    /e-geod-\d+/i.test(text)
  ) {
    task = "gene_expression_genes_in_experiment";
    confidence = 0.8;
    notes += " | Classified as gene_expression_genes_in_experiment (DE genes in experiment)";
  } else if (
    // genes_in_experiment: "genes in E-GEOD-76" (broader: genes + in + experiment ID)
    lowered.includes("genes") &&
    lowered.includes("in") &&
    /e-(?:geod|mtab)-\d+/i.test(text)
  ) {
    task = "gene_expression_genes_in_experiment";
    confidence = 0.75;
    notes += " | Classified as gene_expression_genes_in_experiment (genes in experiment ID)";
  } else if (
    // experiments_for_gene: "where is DUSP2 upregulated", "which experiments show DE of X"
    (lowered.includes("where is") || lowered.includes("which experiments") || lowered.includes("experiments where") || lowered.includes("experiments for")) &&
    (lowered.includes("upregulated") || lowered.includes("downregulated") || lowered.includes("differentially expressed") || lowered.includes("expression") || lowered.includes("gene"))
  ) {
    task = "gene_expression_experiments_for_gene";
    confidence = 0.75;
    notes += " | Classified as gene_expression_experiments_for_gene (experiments for gene)";
  } else if (
    // experiments_for_gene: "find experiments for gene X", "DE of DUSP2"
    (lowered.includes("experiments for") || lowered.includes("experiments with")) &&
    (lowered.includes("gene") || lowered.includes("upregulated") || lowered.includes("downregulated"))
  ) {
    task = "gene_expression_experiments_for_gene";
    confidence = 0.7;
    notes += " | Classified as gene_expression_experiments_for_gene (experiments for gene)";
  } else if (
    // cross_dataset_summary: "summarize DUSP2 across experiments", "DUSP2 DE summary"
    (lowered.includes("summarize") || lowered.includes("summary") || lowered.includes("across experiments")) &&
    (lowered.includes("gene") || lowered.includes("expression") || /\b[A-Z][a-zA-Z0-9]{1,8}\b/.test(text))
  ) {
    task = "gene_expression_gene_cross_dataset_summary";
    confidence = 0.7;
    notes += " | Classified as gene_expression_gene_cross_dataset_summary";
  } else if (
    // genes_agreement: "genes upregulated in multiple experiments", "genes that agree"
    (lowered.includes("agree") || lowered.includes("same direction") || lowered.includes("multiple experiments")) &&
    (lowered.includes("gene") || lowered.includes("upregulated") || lowered.includes("downregulated"))
  ) {
    task = "gene_expression_genes_agreement";
    confidence = 0.75;
    notes += " | Classified as gene_expression_genes_agreement";
  } else if (
    // genes_discordance: "genes in opposite directions", "genes that disagree"
    (lowered.includes("discord") || lowered.includes("opposite direction") || lowered.includes("disagree"))
  ) {
    task = "gene_expression_genes_discordance";
    confidence = 0.75;
    notes += " | Classified as gene_expression_genes_discordance";
  } else if (
    // NDE path: "datasets about X" or "find datasets about X [that contain gene expression]"
    // Route to dataset_search so ontology/kw can fill condition; GXA links when identifier is GSE.
    (lowered.includes("about") && (lowered.includes("datasets") || lowered.includes("dataset"))) &&
    (() => {
      const aboutMatch = lowered.match(/about\s+(\w+(?:\s+\w+){0,2})/);
      const phrase = aboutMatch?.[1]?.trim() ?? "";
      const stop = new Set(["gene", "expression", "data", "that", "contain", "what", "which", "list"]);
      const words = phrase.split(/\s+/).filter((w) => w.length > 1 && !stop.has(w));
      return words.length > 0;
    })()
  ) {
    task = "dataset_search";
    confidence = 0.8;
    notes += " | Classified as dataset_search (datasets about condition → NDE + GXA links)";
  } else if (
    // gene_expression_dataset_search: "gene expression datasets", "list experiments", "gene expression experiments about X"
    (lowered.includes("gene expression") || lowered.includes("expression dataset") ||
      lowered.includes("differential expression") || lowered.includes("expression experiment")) &&
    (lowered.includes("dataset") || lowered.includes("list") || lowered.includes("what") || lowered.includes("which") || lowered.includes("experiments"))
  ) {
    task = "gene_expression_dataset_search";
    confidence = 0.75;
    notes += " | Classified as gene_expression_dataset_search (expression coverage)";
  } else if (lowered.includes("dataset") || lowered.includes("study")) {
    task = "dataset_search";
    confidence = 0.75;
    notes += " | Classified as dataset_search (mentions dataset/study)";
  } else {
    // Fallback: dataset_search with lower confidence
    task = "dataset_search";
    confidence = 0.55;
    notes += " | Defaulted to dataset_search (low confidence)";
  }

  const updatedIntent: Intent = {
    ...baseIntent,
    task,
    slots,
    confidence,
    notes,
  };

  return { intent: updatedIntent };
}







