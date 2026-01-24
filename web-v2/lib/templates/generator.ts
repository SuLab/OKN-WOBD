import type { ContextPack } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import { getTemplateForIntent } from "./registry";

export interface TemplateGenerationResult {
  ok: boolean;
  query?: string;
  error?: string;
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
  const requiredSlots = packTemplateMeta?.required_slots ?? [];

  for (const slot of requiredSlots) {
    if (slots[slot] === undefined || slots[slot] === null || slots[slot] === "") {
      return {
        ok: false,
        error: `Missing required slot '${slot}' for template '${template.id}'`,
      };
    }
  }

  try {
    const query = await template.generate(intent, pack);
    return { ok: true, query };
  } catch (error: any) {
    return {
      ok: false,
      error: error.message || "Template generation failed",
    };
  }
}







