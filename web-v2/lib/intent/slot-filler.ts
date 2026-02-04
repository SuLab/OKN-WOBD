import type { Intent } from "@/types";

// Very lightweight heuristic slot filling.
// Phase 4 can add LLM-based slot filling if needed.

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







