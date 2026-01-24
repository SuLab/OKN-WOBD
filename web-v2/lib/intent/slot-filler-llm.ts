import type { Intent } from "@/types";

export interface SlotFillResult {
  intent: Intent;
  used_llm: boolean;
  error?: string;
}

/**
 * LLM-assisted slot filling for template intents.
 *
 * This calls the Tool Service LLM proxy endpoint (/api/tools/llm/complete)
 * and expects a strict JSON object in the completion:
 *
 * {
 *   "keywords": ["influenza", "vaccine"],
 *   "limit": 50
 * }
 */
export async function fillSlotsWithLLM(
  text: string,
  intent: Intent,
  llmEndpointUrl: string
): Promise<SlotFillResult> {
  // Only apply to dataset_search templates for now
  if (intent.task !== "dataset_search" || intent.lane !== "template") {
    return { intent, used_llm: false };
  }

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

    // Use shared key if available (server-side), otherwise use placeholder session_id
    const useShared = typeof process !== "undefined" && !!process.env.ANTHROPIC_SHARED_API_KEY;

    const body = {
      provider: "anthropic",
      model: "claude-sonnet-4-5",
      use_shared: useShared,
      session_id: useShared ? undefined : "slot-filler", // Placeholder session_id only if not using shared key
      messages: [
        {
          role: "system",
          content: "You return only strict JSON. Never include explanations."
        },
        {
          role: "user",
          content: prompt.trim()
        }
      ],
      temperature: 0.0,
      max_tokens: 200
    };

    const resp = await fetch(llmEndpointUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      let errText = "";
      try {
        errText = JSON.stringify(await resp.json());
      } catch {
        errText = await resp.text();
      }
      return {
        intent,
        used_llm: false,
        error: `LLM call failed: ${resp.status} ${errText}`
      };
    }

    const data = await resp.json();
    const textResponse: string = data.text || "";

    let parsed: { keywords?: string[]; limit?: number };
    try {
      parsed = JSON.parse(textResponse);
    } catch {
      return {
        intent,
        used_llm: false,
        error: "Failed to parse LLM JSON for slot filling"
      };
    }

    const newSlots = { ...(intent.slots || {}) };

    if (Array.isArray(parsed.keywords) && parsed.keywords.length > 0) {
      newSlots.keywords = parsed.keywords.join(" ");
      (newSlots as any).keywords_list = parsed.keywords;
    }

    if (typeof parsed.limit === "number" && Number.isFinite(parsed.limit)) {
      newSlots.limit = parsed.limit;
    }

    const updatedIntent: Intent = {
      ...intent,
      slots: newSlots,
      notes: `${intent.notes || ""} | slots refined by LLM`.trim()
    };

    return { intent: updatedIntent, used_llm: true };
  } catch (error: any) {
    return {
      intent,
      used_llm: false,
      error: error.message || "Unexpected error in LLM slot filling"
    };
  }
}







