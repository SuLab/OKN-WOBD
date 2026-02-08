import type { Intent } from "@/types";

// Very lightweight heuristic slot filling.
// Phase 5: GXA slot extraction (experiment_id, gene_symbols, direction).

const GXA_TASKS = [
  "gene_expression_dataset_search",
  "gene_expression_genes_in_experiment",
  "gene_expression_experiments_for_gene",
  "gene_expression_gene_cross_dataset_summary",
  "gene_expression_genes_agreement",
  "gene_expression_genes_discordance",
] as const;

// Experiment accession pattern: E-GEOD-12345 or E-MTAB-123
const EXPERIMENT_ID_REGEX = /E-(?:GEOD|MTAB)-[\d]+/gi;

// Gene symbol pattern: 2-10 alphanumeric, starts with letter (DUSP2, TP53, Dusp2, Fhl1)
// Exclude common English words that match the pattern
const GENE_SYMBOL_BLOCKLIST = new Set([
  "limit", "what", "which", "where", "list", "show", "find", "gene", "genes",
  "experiment", "experiments", "dataset", "datasets", "expression", "summary",
  "across", "multiple", "same", "opposite", "direction", "directions",
  "summarize", "differential", "differentially", "upregulated", "downregulated",
]);

// Condition/disease phrase stopwords (avoid "about gene", "about expression")
const CONDITION_PHRASE_STOP = new Set([
  "gene", "expression", "data", "that", "contain", "what", "which", "list", "experiments",
]);

// Known disease/condition -> EFO numeric ID (for GXA Study--studies-->Disease filter)
const DISEASE_TO_EFO: Record<string, string[]> = {
  influenza: ["0001072"],
  "heart disease": ["0001461"],
  "heart failure": ["0001645"],
  cancer: ["0000618"],
  diabetes: ["0001360"],
  covid: ["0000644"],
  "covid-19": ["0000644"],
};

function extractExperimentId(text: string): string | undefined {
  const match = text.match(EXPERIMENT_ID_REGEX);
  return match ? match[0].toUpperCase() : undefined;
}

function extractGeneSymbols(text: string): string[] {
  // Match potential gene symbols: DUSP2, TP53, Dusp2, BRCA1, etc.
  const matches = text.match(/\b([A-Z][a-zA-Z0-9]{1,9})\b/g) ?? [];
  const filtered = matches.filter((m) => !GENE_SYMBOL_BLOCKLIST.has(m.toLowerCase()));
  // Sort so gene-like symbols (2-8 chars) come first; avoid sentence verbs like "Summarize"
  return [...new Set(filtered)].sort((a, b) => {
    const aGeneLike = a.length >= 2 && a.length <= 8;
    const bGeneLike = b.length >= 2 && b.length <= 8;
    if (aGeneLike && !bGeneLike) return -1;
    if (!aGeneLike && bGeneLike) return 1;
    return a.length - b.length;
  });
}

/**
 * Extract disease/condition phrases from "about X", "related to X", "for X" for GXA filters.
 * Returns factor_terms (text match on contrast labels) and disease_efo_ids when we have a mapping.
 */
function extractDiseaseOrConditionPhrases(lower: string): { factorTerms: string[]; diseaseEfoIds: string[] } {
  const factorTerms: string[] = [];
  const diseaseEfoIds: string[] = [];
  const patterns = [
    /about\s+(\w+(?:\s+\w+){0,2})/,
    /related\s+to\s+(\w+(?:\s+\w+){0,2})/,
    /(?:datasets?|experiments?)\s+for\s+(\w+(?:\s+\w+){0,2})/,
  ];
  for (const re of patterns) {
    const m = lower.match(re);
    const phrase = m?.[1]?.trim().toLowerCase() ?? "";
    const words = phrase.split(/\s+/).filter((w) => w.length > 1 && !CONDITION_PHRASE_STOP.has(w));
    if (words.length > 0) {
      const term = words.join(" ");
      if (!factorTerms.includes(term)) factorTerms.push(term);
      const efo = DISEASE_TO_EFO[term];
      if (efo) for (const id of efo) if (!diseaseEfoIds.includes(id)) diseaseEfoIds.push(id);
    }
  }
  return { factorTerms, diseaseEfoIds };
}

export function fillSlots(intent: Intent, text: string): Intent {
  const slots = { ...(intent.slots || {}) };

  // Default keywords: full text
  if (slots.keywords === undefined || slots.keywords === null) {
    slots.keywords = text;
  }

  // For entity_lookup, prefer a shorter q (strip leading command)
  if (intent.task === "entity_lookup") {
    const withoutCommand = text.replace(/^\/entity\s+/i, "").trim();
    if (withoutCommand) {
      slots.q = withoutCommand;
    } else {
      slots.q = text;
    }
  }

  // Phase 5: GXA slot extraction
  if (GXA_TASKS.includes(intent.task as (typeof GXA_TASKS)[number])) {
    const experimentId = extractExperimentId(text);
    if (experimentId && !slots.experiment_id) {
      slots.experiment_id = experimentId;
    }

    const geneSymbols = extractGeneSymbols(text);
    if (geneSymbols.length > 0) {
      if (
        intent.task === "gene_expression_experiments_for_gene" &&
        !slots.gene_symbols
      ) {
        slots.gene_symbols = geneSymbols;
      }
      if (
        intent.task === "gene_expression_gene_cross_dataset_summary" &&
        !slots.gene_symbol
      ) {
        slots.gene_symbol = geneSymbols[0];
      }
    }

    // Direction: upregulated / downregulated
    const lower = text.toLowerCase();
    if (!slots.direction) {
      if (lower.includes("upregulated") || lower.includes("up-regulation") || lower.includes("up regulation")) {
        slots.direction = "up";
      } else if (lower.includes("downregulated") || lower.includes("down-regulation") || lower.includes("down regulation")) {
        slots.direction = "down";
      }
    }

    // Disease/condition for GXA: extract "about X", "related to X", "for X" -> factor_terms and optional disease_efo_ids
    const { factorTerms, diseaseEfoIds } = extractDiseaseOrConditionPhrases(lower);
    if (factorTerms.length > 0 && !slots.factor_terms?.length) {
      slots.factor_terms = factorTerms;
    }
    if (diseaseEfoIds.length > 0 && !slots.disease_efo_ids?.length) {
      slots.disease_efo_ids = diseaseEfoIds;
    }
  }

  // NDE↔GXA bridge: when user asks for datasets that "contain gene expression [data]", attach GXA coverage to NDE results
  if (intent.task === "dataset_search") {
    const lower = text.toLowerCase();
    const wantsGxaBridge =
      lower.includes("contain gene expression") ||
      lower.includes("gene expression data") ||
      lower.includes("with gene expression") ||
      lower.includes("that have gene expression");
    if (wantsGxaBridge) {
      slots.include_gxa_bridge = true;
    }
  }

  // Simple limit detection: "... limit 10"
  const limitMatch = text.match(/limit\s+(\d+)/i);
  if (limitMatch) {
    const limit = parseInt(limitMatch[1], 10);
    if (!Number.isNaN(limit)) {
      slots.limit = limit;
    }
  }

  return {
    ...intent,
    slots,
  };
}







