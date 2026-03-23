import type { ContextPack } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { getTemplateForIntent } from "./registry";

export interface TemplateGenerationResult {
  ok: boolean;
  query?: string;
  error?: string;
  relatedQueries?: { nde_disease_coverage?: string };
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

  // gene_expression_genes_agreement: when ontology_workflow supplies disease (health_conditions), no extra required slots
  if (template.id === "gene_expression_genes_agreement" && intent.ontology_workflow) {
    const healthConditions = slots.health_conditions;
    const ontologyState = slots.ontology_state as { grounded_mondo_terms?: unknown[] } | undefined;
    const hasDisease =
      (Array.isArray(healthConditions) && healthConditions.length > 0) ||
      (ontologyState?.grounded_mondo_terms?.length ?? 0) > 0;
    if (hasDisease) {
      requiredSlots = []; // template has required_slots: [] already; ensure we don't require anything else
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
    const result = await template.generate(intent, pack);
    if (typeof result === "object" && result !== null && "query" in result) {
      return {
        ok: true,
        query: result.query,
        relatedQueries: result.relatedQueries,
      };
    }
    return { ok: true, query: result as string };
  } catch (error: any) {
    return {
      ok: false,
      error: error.message || "Template generation failed",
    };
  }
}







