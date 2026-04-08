import type { ContextPack } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import type { MondoExpansionStats } from "@/lib/ontology/mondo-descendants-ols";
import type { TemplateGenerateResult } from "@/lib/templates/generate-types";
import { getTemplateForIntent } from "./registry";

/** JSON shape for intent-to-sparql (snake_case). */
export type MondoExpansionStatsJson = {
  roots_expanded: number;
  mondo_iris_in_filter: number;
  iri_cap: number;
  truncated: boolean;
  highlight_label_count: number;
  highlight_label_cap: number;
  /** False when expanded IRIs were not used in SPARQL (keyword fallback). */
  applied_to_sparql_filter?: boolean;
};

export interface TemplateGenerationResult {
  ok: boolean;
  query?: string;
  error?: string;
  /** MONDO subclass labels from OLS when dataset_search used expansion (UI highlighting). */
  mondo_expansion_highlight_labels?: string[];
  mondo_expansion_stats?: MondoExpansionStatsJson;
}

function statsToJson(s: MondoExpansionStats): MondoExpansionStatsJson {
  const j: MondoExpansionStatsJson = {
    roots_expanded: s.rootsExpanded,
    mondo_iris_in_filter: s.mondoIrisInFilter,
    iri_cap: s.iriCap,
    truncated: s.truncated,
    highlight_label_count: s.highlightLabelCount,
    highlight_label_cap: s.highlightLabelCap,
  };
  if (s.appliedToSparqlFilter === false) {
    j.applied_to_sparql_filter = false;
  }
  return j;
}

function normalizeTemplateOutput(raw: string | TemplateGenerateResult): {
  query: string;
  mondo_expansion_highlight_labels?: string[];
  mondo_expansion_stats?: MondoExpansionStatsJson;
} {
  if (typeof raw === "string") {
    return { query: raw };
  }
  const labels = raw.mondoExpansionHighlightLabels;
  return {
    query: raw.query,
    mondo_expansion_highlight_labels:
      labels && labels.length > 0 ? labels : undefined,
    mondo_expansion_stats: raw.mondoExpansionStats ? statsToJson(raw.mondoExpansionStats) : undefined,
  };
}

export async function generateSPARQLFromIntent(intent: Intent, pack: ContextPack): Promise<TemplateGenerationResult> {
  const template = getTemplateForIntent(intent);
  if (!template) {
    return {
      ok: false,
      error: `No template found for task '${intent.task}'`,
    };
  }

  // Check required slots
  const slots = intent.slots || {};
  const packTemplateMeta = pack.templates?.find(t => t.id === template.id);
  let requiredSlots = packTemplateMeta?.required_slots ?? [];

  // dataset_search / geo_dataset_search: when used in ontology workflow with health_conditions, keywords is not required
  if ((template.id === "dataset_search" || template.id === "geo_dataset_search") && intent.ontology_workflow) {
    const healthConditions = slots.health_conditions;
    const hasHealthConditions = Array.isArray(healthConditions) && healthConditions.length > 0;
    if (hasHealthConditions) {
      requiredSlots = requiredSlots.filter((s: string) => s !== "keywords");
    }
  }

  for (const slot of requiredSlots) {
    if (slots[slot] === undefined || slots[slot] === null || slots[slot] === "") {
      return {
        ok: false,
        error: `Missing required slot '${slot}' for template '${template.id}'`,
      };
    }
  }

  try {
    const raw = await template.generate(intent, pack);
    const { query, mondo_expansion_highlight_labels, mondo_expansion_stats } =
      normalizeTemplateOutput(raw);
    return { ok: true, query, mondo_expansion_highlight_labels, mondo_expansion_stats };
  } catch (error: any) {
    return {
      ok: false,
      error: error.message || "Template generation failed",
    };
  }
}







