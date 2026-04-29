/**
 * Structured stderr logging for `/api/tools/sparql/execute` when the caller identifies
 * a template task (dashboard templated flows). Gated by server env OKN_SPARQL_LOG.
 */

import { createHash } from "crypto";

function loggingEnabled(): boolean {
  const v = process.env.OKN_SPARQL_LOG?.trim()?.toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

/** Short stable fingerprint of SPARQL text (avoid logging full queries in prod). */
export function sparqlQueryFingerprint(query: string): string {
  return createHash("sha256").update(query, "utf8").digest("hex").slice(0, 12);
}

/** Coarse class for telemetry (substring heuristics on user-facing messages). */
export function classifyExecuteError(error: string | undefined): string {
  if (!error) return "none";
  if (/timed out|took too long to respond/i.test(error)) return "timeout";
  if (/Invalid SPARQL query|mismatched input/i.test(error)) return "sparql_parse";
  const m = error.match(/SPARQL endpoint error:\s*(\d{3})\b/);
  if (m?.[1]) return `http_${m[1]}`;
  return "other";
}

export interface TemplateSparqlLogPayload {
  run_id: string;
  pack_id?: string;
  endpoint: string;
  timeout_s: number;
  mode?: string;
  graphs: unknown;
  query_byte_length: number;
  query_sha12: string;
  first_attempt_latency_ms: number;
  /** Present only when federation was called twice after repair retry. */
  second_attempt_latency_ms?: number | null;
  outcome: "success" | "failure";
  final_error_class: string;
  repair_call_after_first_failure?: boolean;
  repair_returned_candidate?: boolean;
  repair_candidate_valid_for_execute?: boolean;
  repair_retries_federation?: boolean;
  repair_changes?: string[];
  row_count: number;
}

export function maybeLogTemplateSparqlExecute(
  template_task: unknown,
  payload: TemplateSparqlLogPayload,
): void {
  if (!loggingEnabled()) return;
  if (typeof template_task !== "string" || !template_task.trim()) return;

  const line = JSON.stringify({
    event: "template_sparql_execute",
    template_task: template_task.trim().slice(0, 160),
    ...payload,
  });
  console.info(line);
}
