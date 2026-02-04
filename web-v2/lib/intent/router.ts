import type { Intent } from "@/types";
import type { ContextPack } from "@/lib/context-packs/types";

export type Lane = "template" | "open" | "raw";

export interface RoutingOverrides {
  lane?: Lane;
  context_pack?: string;
  graph_mode?: "federated" | "single_graph";
  graphs?: string[];
}

export interface RoutingDecision {
  lane: Lane;
  context_pack: string;
  graph_mode: "federated" | "single_graph";
  graphs: string[];
  notes: string;
}

// Parse slash commands and @pack mentions from the user text
export function parseOverridesFromText(text: string): RoutingOverrides {
  const trimmed = text.trim();
  const overrides: RoutingOverrides = {};

  // Lane overrides
  if (trimmed.startsWith("/sparql")) {
    overrides.lane = "raw";
  } else if (trimmed.startsWith("/open")) {
    overrides.lane = "open";
  }

  // Context pack mentions: @wobd, @protookn, etc.
  const packMatch = trimmed.match(/@([a-zA-Z0-9_-]+)/);
  if (packMatch) {
    overrides.context_pack = packMatch[1];
  }

  // Future: parse /dataset, /entity, etc. here if needed

  return overrides;
}

export function buildInitialIntent(
  text: string,
  pack: ContextPack,
  overrides: RoutingOverrides
): Intent {
  const lane: Lane =
    overrides.lane ??
    pack.intent_routing?.default_lane ??
    "template";

  const graph_mode: "federated" | "single_graph" =
    overrides.graph_mode ?? "federated";

  const graphs: string[] =
    overrides.graphs && overrides.graphs.length > 0
      ? overrides.graphs
      : pack.graphs.default_shortnames;

  // Very simple task guess based on slash commands; Phase 4 can add more
  let task = "dataset_search";
  if (text.trim().startsWith("/entity")) {
    task = "entity_lookup";
  }

  const intent: Intent = {
    lane,
    task,
    context_pack: pack.id,
    graph_mode,
    graphs,
    slots: {
      // Default: use raw text as keywords; slot-filler can refine
      keywords: text,
      q: text,
    },
    confidence: 0.5,
    notes: "Initial heuristic intent; may be refined by classifier/slot-filler",
  };

  return intent;
}

export function makeRoutingDecision(
  intent: Intent,
  pack: ContextPack
): RoutingDecision {
  const openThreshold = pack.intent_routing?.open_query_threshold ?? 0.55;

  let lane: Lane = intent.lane;
  let notes = intent.notes || "";

  if (lane === "template" && intent.confidence < openThreshold) {
    lane = "open";
    notes += ` | Fell back to open query (confidence ${intent.confidence.toFixed(
      2
    )} < threshold ${openThreshold})`;
  }

  return {
    lane,
    context_pack: intent.context_pack,
    graph_mode: intent.graph_mode,
    graphs: intent.graphs,
    notes,
  };
}







