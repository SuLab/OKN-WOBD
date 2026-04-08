import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import type { TemplateGenerateResult } from "@/lib/templates/generate-types";
import { buildDatasetSearchQuery } from "./dataset_search";

export const GEO_DATASET_SEARCH_TEMPLATE_ID = "geo_dataset_search";

export const geoDatasetSearchTemplate: TemplateDefinition = {
  id: GEO_DATASET_SEARCH_TEMPLATE_ID,
  description: "Find NCBI GEO datasets in NDE by keywords with optional health condition, host species, and pathogen species filters",
  required_slots: [],
  optional_slots: ["health_condition", "mondo_expand_descendants", "infectious_agent", "species"],
};

/**
 * Build SPARQL for NDE restricted to NCBI GEO datasets (same schema.org as other NDE resources).
 * Delegates to dataset_search with geoOnly: true.
 */
export async function buildGeoDatasetSearchQuery(
  intent: Intent,
  pack: ContextPack
): Promise<TemplateGenerateResult> {
  return buildDatasetSearchQuery(intent, pack, { geoOnly: true });
}
