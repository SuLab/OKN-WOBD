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
  if (lowered.startsWith("/entity")) {
    task = "entity_lookup";
    confidence = 0.9;
    notes += " | Classified as entity_lookup via /entity command";
  } else if (
    (lowered.includes("gene expression") || lowered.includes("expression dataset") ||
      lowered.includes("differential expression") || lowered.includes("expression experiment")) &&
    (lowered.includes("dataset") || lowered.includes("list") || lowered.includes("what") || lowered.includes("which"))
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







