import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";

export const ENTITY_LOOKUP_TEMPLATE_ID = "entity_lookup";

export const entityLookupTemplate: TemplateDefinition = {
  id: ENTITY_LOOKUP_TEMPLATE_ID,
  description: "Resolve CURIE/URI/label to entity",
  required_slots: ["q"],
};

export function buildEntityLookupQuery(intent: Intent, pack: ContextPack): string {
  const prefixes = pack.prefixes;
  const slots = intent.slots || {};
  const q: string = (slots.q ?? "").toString();
  const escaped = q.replace(/"/g, '\\"');

  let query = "";
  for (const [prefix, uri] of Object.entries(prefixes)) {
    query += `PREFIX ${prefix}: <${uri}>\n`;
  }

  // Simple heuristic:
  // - If q looks like a URI, match subject directly
  // - Otherwise, search schema:name / rdfs:label
  const looksLikeUri = /^https?:\/\//i.test(q);

  if (looksLikeUri) {
    query += `
SELECT ?subject ?name ?type
WHERE {
  BIND(<${q}> AS ?subject)
  OPTIONAL { ?subject schema:name ?name }
  OPTIONAL { ?subject a ?type }
}
LIMIT ${Math.min((intent.slots?.limit as number) || 10, pack.guardrails.max_limit)}
    `.trim();
  } else {
    query += `
SELECT ?subject ?name ?type
WHERE {
  ?subject a ?type .
  OPTIONAL { ?subject schema:name ?name }
  FILTER(
    (BOUND(?name) && REGEX(STR(?name), "${escaped}", "i"))
    || REGEX(STR(?subject), "${escaped}", "i")
  )
}
LIMIT ${Math.min((intent.slots?.limit as number) || 25, pack.guardrails.max_limit)}
    `.trim();
  }

  return query;
}







