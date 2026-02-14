import type { ContextPack } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import type { SPARQLResult } from "@/types";

export const PACK_ID = "wobd";

export const GXA_TASKS = [
  "gene_expression_dataset_search",
  "gene_expression_genes_in_experiment",
  "gene_expression_experiments_for_gene",
  "gene_expression_gene_cross_dataset_summary",
  "gene_expression_genes_agreement",
  "gene_expression_genes_discordance",
] as const;

const DATASET_SEARCH_TEMPLATE_ID = "dataset_search";
const GEO_DATASET_SEARCH_TEMPLATE_ID = "geo_dataset_search";
const NDE_TEMPLATE_IDS = [DATASET_SEARCH_TEMPLATE_ID, GEO_DATASET_SEARCH_TEMPLATE_ID];

export function buildIntent(
  templateId: string,
  slots: Record<string, string | string[]>,
  pack: ContextPack
): Intent {
  const graphs = GXA_TASKS.includes(templateId as (typeof GXA_TASKS)[number])
    ? ["gene-expression-atlas-okn"]
    : NDE_TEMPLATE_IDS.includes(templateId)
      ? ["nde"]
      : pack.graphs.default_shortnames;

  return {
    lane: "template",
    task: templateId,
    context_pack: pack.id,
    graph_mode: "federated",
    graphs,
    slots: { ...slots },
    confidence: 0.9,
    notes: "Dashboard form",
  };
}

export function isNDEShape(vars: string[]): boolean {
  const set = new Set(vars);
  return set.has("name") && (set.has("description") || set.has("identifier"));
}

export interface RunQueryParams {
  templateId: string;
  slots: Record<string, string | string[]>;
  pack: ContextPack;
  signal?: AbortSignal;
}

export interface RunQueryResult {
  results: SPARQLResult | null;
  error: string | null;
  /** When "only gene expression" filter returns no rows but unfiltered had results (drug_datasets). */
  filteredEmptyHint?: string;
}

const DRUG_DATASETS_TEMPLATE_ID = "drug_datasets";

export async function runTemplateQuery({
  templateId,
  slots,
  pack,
  signal,
}: RunQueryParams): Promise<RunQueryResult> {
  if (templateId === DRUG_DATASETS_TEMPLATE_ID) {
    const drugs = Array.isArray(slots.drug)
      ? (slots.drug as string[]).map((d) => String(d).trim()).filter(Boolean)
      : typeof slots.drug === "string" && slots.drug.trim()
        ? [slots.drug.trim()]
        : [];
    if (drugs.length === 0) {
      return { results: null, error: "At least one drug name is required." };
    }
    const onlyGeneExpression =
      slots.only_gene_expression === "true" ||
      (Array.isArray(slots.only_gene_expression) && slots.only_gene_expression[0] === "true");
    const maxResultsRaw = Array.isArray(slots.max_results)
      ? slots.max_results[0]
      : slots.max_results;
    const maxResults =
      typeof maxResultsRaw === "string" && maxResultsRaw.trim() !== ""
        ? Math.min(Math.max(1, parseInt(maxResultsRaw, 10) || 500), 500)
        : undefined;
    const res = await fetch("/api/tools/drug-datasets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drugs, onlyGeneExpression, maxResults }),
      signal,
    });
    const data = await res.json();
    if (signal?.aborted) return { results: null, error: "Query was cancelled." };
    if (data.error && !data.results) {
      return { results: null, error: data.error };
    }
    if (!data.results) {
      return { results: null, error: data.error || "No results from pipeline." };
    }
    return {
      results: data.results,
      error: null,
      filteredEmptyHint: data.filtered_empty_hint ?? undefined,
    };
  }

  const intent = buildIntent(templateId, slots, pack);

  const sparqlRes = await fetch("/api/tools/nl/intent-to-sparql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent, pack_id: PACK_ID }),
    signal,
  });
  if (!sparqlRes.ok) {
    const err = await sparqlRes.json();
    throw new Error(err.error || "SPARQL generation failed");
  }
  const { query } = await sparqlRes.json();
  if (!query) throw new Error("No query returned");

  const execRes = await fetch("/api/tools/sparql/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      pack_id: PACK_ID,
      mode: intent.graph_mode,
      graphs: intent.graphs,
      attempt_repair: true,
      run_preflight: false,
      debug: true,
    }),
    signal,
  });
  const execData = await execRes.json();

  if (signal?.aborted) {
    return { results: null, error: "Query was cancelled." };
  }

  if (!execRes.ok || execData.error) {
    return {
      results: null,
      error: execData.error || "Query execution failed",
    };
  }

  const bindings = execData.bindings ?? execData.result?.results?.bindings ?? [];
  const head = execData.head ?? execData.result?.head;
  const vars = Array.isArray(head?.vars) ? head.vars : (bindings[0] ? Object.keys(bindings[0]) : []);

  return {
    results: { head: { vars }, results: { bindings } },
    error: null,
  };
}
