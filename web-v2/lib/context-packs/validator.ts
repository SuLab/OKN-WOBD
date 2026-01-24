import { z } from "zod";
import type { ContextPack } from "./types";

const ContextPackSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string().optional(),
  version: z.string(),
  endpoint_mode: z.object({
    default: z.enum(["federated", "direct"]),
    federated_endpoint: z.string().url(),
    direct_endpoints: z.record(z.string()).optional(),
  }),
  graphs: z.object({
    default_shortnames: z.array(z.string()),
    allow_user_select: z.boolean(),
  }),
  prefixes: z.record(z.string()),
  guardrails: z.object({
    max_limit: z.number().positive(),
    timeout_seconds: z.number().positive(),
    max_rows_download: z.number().positive(),
    allow_raw_sparql: z.boolean(),
    allow_open_nl2sparql: z.boolean(),
    allow_service: z.boolean(),
    service_policy: z.enum(["allowlist", "allow_any_frink", "allow_any", "forbid_all"]),
    service_allowlist: z.array(z.string()).optional(),
    forbid_ops: z.array(z.string()),
  }),
  templates: z.array(z.object({
    id: z.string(),
    description: z.string(),
    required_slots: z.array(z.string()),
    optional_slots: z.array(z.string()).optional(),
  })).optional(),
  schema_hints: z.object({
    example_queries: z.array(z.string()).optional(),
    common_predicates: z.array(z.string()).optional(),
  }).optional(),
  intent_routing: z.object({
    default_lane: z.enum(["template", "open"]),
    open_query_threshold: z.number().min(0).max(1),
  }).optional(),
});

export function validateContextPack(pack: unknown): { valid: boolean; errors?: z.ZodError } {
  try {
    ContextPackSchema.parse(pack);
    return { valid: true };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { valid: false, errors: error };
    }
    throw error;
  }
}






