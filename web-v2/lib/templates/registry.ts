import type { ContextPack } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import {
  DATASET_SEARCH_TEMPLATE_ID,
  datasetSearchTemplate,
  buildDatasetSearchQuery,
} from "./templates/dataset_search";
import {
  ENTITY_LOOKUP_TEMPLATE_ID,
  entityLookupTemplate,
  buildEntityLookupQuery,
} from "./templates/entity_lookup";

export type TemplateId = typeof DATASET_SEARCH_TEMPLATE_ID | typeof ENTITY_LOOKUP_TEMPLATE_ID;

type TemplateGenerator = (intent: Intent, pack: ContextPack) => string | Promise<string>;

interface RegisteredTemplate {
  id: TemplateId;
  generate: TemplateGenerator;
}

const TEMPLATE_REGISTRY: Record<string, RegisteredTemplate> = {
  [DATASET_SEARCH_TEMPLATE_ID]: {
    id: DATASET_SEARCH_TEMPLATE_ID,
    generate: buildDatasetSearchQuery,
  },
  [ENTITY_LOOKUP_TEMPLATE_ID]: {
    id: ENTITY_LOOKUP_TEMPLATE_ID,
    generate: buildEntityLookupQuery,
  },
};

export function getTemplateForIntent(intent: Intent): RegisteredTemplate | null {
  // Use intent.task directly; later this can use richer routing logic
  const id = intent.task as TemplateId;
  const entry = TEMPLATE_REGISTRY[id];
  return entry || null;
}

export function listTemplateDefinitionsForPack(pack: ContextPack) {
  // Combine pack.templates metadata with built-in ones if needed
  return pack.templates ?? [datasetSearchTemplate, entityLookupTemplate];
}







