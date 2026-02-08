import type { Intent } from "@/types";

export interface SlotFillResult {
  intent: Intent;
  used_llm: boolean;
  error?: string;
}

const GXA_TASKS = [
  "gene_expression_dataset_search",
  "gene_expression_genes_in_experiment",
  "gene_expression_experiments_for_gene",
  "gene_expression_gene_cross_dataset_summary",
  "gene_expression_genes_agreement",
  "gene_expression_genes_discordance",
] as const;

function isGxaTask(task: string): task is (typeof GXA_TASKS)[number] {
  return GXA_TASKS.includes(task as (typeof GXA_TASKS)[number]);
}

/**
 * LLM-assisted slot filling for template intents.
 *
 * For dataset_search: extracts keywords, limit.
 * For GXA tasks (Phase 5): extracts experiment_id, gene_symbols, gene_symbol,
 * organism_taxon_ids, tissue_uberon_ids, factor_terms, disease_efo_ids, direction, limit.
 */
export async function fillSlotsWithLLM(
  text: string,
  intent: Intent,
  llmEndpointUrl: string
): Promise<SlotFillResult> {
  if (intent.lane !== "template") {
    return { intent, used_llm: false };
  }

  if (intent.task === "dataset_search") {
    return fillSlotsDatasetSearch(text, intent, llmEndpointUrl);
  }

  if (isGxaTask(intent.task)) {
    return fillSlotsGXA(text, intent, llmEndpointUrl);
  }

  return { intent, used_llm: false };
}

async function fillSlotsDatasetSearch(
  text: string,
  intent: Intent,
  llmEndpointUrl: string
): Promise<SlotFillResult> {
  try {
    const prompt = `
You extract structured parameters for a SPARQL dataset search template.

User question:
"${text}"

Current intent (JSON):
${JSON.stringify(intent, null, 2)}

Return ONLY a JSON object with this exact shape, no extra text:

{
  "keywords": ["list", "of", "short", "terms"],
  "limit": 50
}

Rules:
- "keywords" should be 1–5 short terms or phrases capturing the main topic
  (e.g., from "Show datasets related to influenza vaccines" -> ["influenza","vaccine"]).
- Do NOT include generic words like "show", "datasets", "related", "to".
- "limit" should be an integer (default 50 if not obvious from the question).
`;

    const resp = await callLLM(llmEndpointUrl, prompt);
    if (!resp.ok) {
      const errText = await resp.text().catch(() => "Unknown error");
      return { intent, used_llm: false, error: `LLM call failed: ${resp.status} ${errText}` };
    }

    const data = await resp.json();
    const parsed = parseJson<{ keywords?: string[]; limit?: number }>(data.text || "");
    if (!parsed) {
      return { intent, used_llm: false, error: "Failed to parse LLM JSON for slot filling" };
    }

    const newSlots = { ...(intent.slots || {}) };
    if (Array.isArray(parsed.keywords) && parsed.keywords.length > 0) {
      newSlots.keywords = parsed.keywords.join(" ");
      (newSlots as Record<string, unknown>).keywords_list = parsed.keywords;
    }
    if (typeof parsed.limit === "number" && Number.isFinite(parsed.limit)) {
      newSlots.limit = parsed.limit;
    }

    return {
      intent: { ...intent, slots: newSlots, notes: `${intent.notes || ""} | slots refined by LLM`.trim() },
      used_llm: true,
    };
  } catch (error: unknown) {
    return {
      intent,
      used_llm: false,
      error: error instanceof Error ? error.message : "Unexpected error in LLM slot filling",
    };
  }
}

async function fillSlotsGXA(
  text: string,
  intent: Intent,
  llmEndpointUrl: string
): Promise<SlotFillResult> {
  try {
    const task = intent.task;
    const slotsSchema = getGxaSlotsSchema(task);
    const prompt = `
You extract structured parameters for a gene expression SPARQL template.

User question:
"${text}"

Current intent (JSON):
${JSON.stringify(intent, null, 2)}

Task: ${task}

Return ONLY a JSON object. Include ONLY the fields that you can extract from the question. Omit fields you cannot determine.

Schema (include only applicable fields):
${slotsSchema}

Rules:
- experiment_id: GEO accession like E-GEOD-76, E-GEOD-23301. Extract if user mentions an experiment.
- gene_symbol or gene_symbols: Gene symbol (e.g. DUSP2, TP53). Use gene_symbol for single-gene tasks, gene_symbols array for multi-gene.
- organism_taxon_ids: NCBITaxon IDs as strings, e.g. ["10090"] for mouse, ["9606"] for human. Map: mouse/Mus musculus->10090, human/Homo sapiens->9606.
- tissue_uberon_ids: UBERON IDs as strings, e.g. ["0002082"] for heart. Map common tissue names to UBERON numeric IDs.
- factor_terms: Text terms for perturbation/factor (e.g. ["surgery", "aortic banding"]). Plain substrings to match.
- disease_efo_ids: EFO disease IDs as strings, e.g. ["0001461"] for heart disease. Use numeric part only.
- direction: "up" or "down" if user asks for upregulated or downregulated.
- limit: integer (default 50).
`;

    const resp = await callLLM(llmEndpointUrl, prompt);
    if (!resp.ok) {
      const errText = await resp.text().catch(() => "Unknown error");
      return { intent, used_llm: false, error: `LLM call failed: ${resp.status} ${errText}` };
    }

    const data = await resp.json();
    const parsed = parseJson<Record<string, unknown>>(data.text || "");
    if (!parsed) {
      return { intent, used_llm: false, error: "Failed to parse LLM JSON for GXA slot filling" };
    }

    const newSlots = { ...(intent.slots || {}) };

    if (parsed.experiment_id && typeof parsed.experiment_id === "string") {
      newSlots.experiment_id = parsed.experiment_id.trim();
    }
    if (parsed.gene_symbol && typeof parsed.gene_symbol === "string") {
      newSlots.gene_symbol = parsed.gene_symbol.trim();
    }
    if (parsed.gene_symbols) {
      const arr = Array.isArray(parsed.gene_symbols)
        ? parsed.gene_symbols.map(String).filter(Boolean)
        : typeof parsed.gene_symbols === "string"
          ? [parsed.gene_symbols]
          : [];
      if (arr.length > 0) newSlots.gene_symbols = arr;
    }
    if (parsed.organism_taxon_ids && Array.isArray(parsed.organism_taxon_ids)) {
      newSlots.organism_taxon_ids = parsed.organism_taxon_ids.map(String).filter(Boolean);
    } else if (parsed.species && Array.isArray(parsed.species)) {
      newSlots.organism_taxon_ids = parsed.species.map(String).filter(Boolean);
    }
    if (parsed.tissue_uberon_ids && Array.isArray(parsed.tissue_uberon_ids)) {
      newSlots.tissue_uberon_ids = parsed.tissue_uberon_ids.map(String).filter(Boolean);
    }
    if (parsed.factor_terms && Array.isArray(parsed.factor_terms)) {
      newSlots.factor_terms = parsed.factor_terms.map(String).filter(Boolean);
    }
    if (parsed.disease_efo_ids && Array.isArray(parsed.disease_efo_ids)) {
      newSlots.disease_efo_ids = parsed.disease_efo_ids.map(String).filter(Boolean);
    }
    if (parsed.direction && typeof parsed.direction === "string") {
      newSlots.direction = parsed.direction.toLowerCase().startsWith("up") ? "up" : "down";
    }
    if (typeof parsed.limit === "number" && Number.isFinite(parsed.limit)) {
      newSlots.limit = parsed.limit;
    }

    return {
      intent: { ...intent, slots: newSlots, notes: `${intent.notes || ""} | GXA slots refined by LLM`.trim() },
      used_llm: true,
    };
  } catch (error: unknown) {
    return {
      intent,
      used_llm: false,
      error: error instanceof Error ? error.message : "Unexpected error in GXA LLM slot filling",
    };
  }
}

function getGxaSlotsSchema(task: string): string {
  const base = `
{
  "experiment_id": "E-GEOD-76",
  "gene_symbol": "DUSP2",
  "gene_symbols": ["DUSP2"],
  "organism_taxon_ids": ["10090"],
  "tissue_uberon_ids": ["0002082"],
  "factor_terms": ["surgery"],
  "disease_efo_ids": ["0001461"],
  "direction": "up",
  "limit": 50
}`;
  if (task === "gene_expression_genes_in_experiment") {
    return base + "\nRequired: experiment_id";
  }
  if (task === "gene_expression_experiments_for_gene" || task === "gene_expression_gene_cross_dataset_summary") {
    return base + "\nRequired: gene_symbol or gene_symbols";
  }
  return base;
}

function callLLM(llmEndpointUrl: string, userContent: string): Promise<Response> {
  const useShared = typeof process !== "undefined" && !!process.env.ANTHROPIC_SHARED_API_KEY;
  return fetch(llmEndpointUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: "anthropic",
      model: "claude-sonnet-4-5",
      use_shared: useShared,
      session_id: useShared ? undefined : "slot-filler",
      messages: [
        { role: "system", content: "You return only strict JSON. Never include explanations." },
        { role: "user", content: userContent.trim() },
      ],
      temperature: 0.0,
      max_tokens: 300,
    }),
  });
}

function parseJson<T>(text: string): T | null {
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}
