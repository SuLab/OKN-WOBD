import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { buildDatasetSearchQuery } from "./dataset_search";

export const GEO_DATASET_SEARCH_TEMPLATE_ID = "geo_dataset_search";

export const geoDatasetSearchTemplate: TemplateDefinition = {
  id: GEO_DATASET_SEARCH_TEMPLATE_ID,
  description: "Find NCBI GEO datasets in NDE by keywords, disease, or organism",
  required_slots: ["keywords"],
};

/**
 * Build SPARQL for NDE restricted to NCBI GEO datasets (same schema.org as other NDE resources).
 * Delegates to dataset_search with geoOnly: true.
 */
export async function buildGeoDatasetSearchQuery(
  intent: Intent,
  pack: ContextPack
): Promise<string> {
  return buildDatasetSearchQuery(intent, pack, { geoOnly: true });
}
