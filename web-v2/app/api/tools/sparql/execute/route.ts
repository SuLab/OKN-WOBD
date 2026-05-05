import { NextResponse } from "next/server";
import { executeSPARQL, injectFromClauses } from "@/lib/sparql/executor";
import { validateSPARQL } from "@/lib/sparql/validator";
import { loadContextPack } from "@/lib/context-packs/loader";
import { runStore } from "@/lib/runs/store";
import { attemptRepair } from "@/lib/sparql/repair";
import { runPreflight } from "@/lib/sparql/preflight";
import {
  classifyExecuteError,
  maybeLogTemplateSparqlExecute,
  sparqlQueryFingerprint,
} from "@/lib/sparql/template-execute-log";

// Simple UUID v4 generator (in production, use a proper library)
function uuidv4(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const {
      query,
      pack_id,
      mode,
      graphs,
      options,
      run_preflight,
      attempt_repair,
      debug,
      /** Dashboard `/template/[id]` only — enables OKN_SPARQL_LOG structured lines. */
      template_task,
    } = body;

    if (!query || typeof query !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid 'query' parameter" },
        { status: 400 }
      );
    }

    const pack = pack_id ? loadContextPack(pack_id) : null;
    if (pack_id && !pack) {
      return NextResponse.json(
        { error: `Context pack not found: ${pack_id}` },
        { status: 404 }
      );
    }

    // Validate query
    const guardrails = pack?.guardrails || {
      forbid_ops: ["INSERT", "DELETE", "LOAD", "CLEAR", "DROP", "CREATE", "MOVE", "COPY", "ADD"],
      max_limit: 500,
    };

    const validation = validateSPARQL(query, guardrails);
    if (!validation.valid) {
      return NextResponse.json(
        { error: "Query validation failed", errors: validation.errors },
        { status: 400 }
      );
    }

    // Use normalized query if available
    let finalQuery = validation.normalized_query || query;

    // Decide routing from the query before we inject FROM (injection adds graphs from intent, which can
    // include gene-expression-atlas-okn for "contain gene expression data" even when the template built an NDE query)
    const gxaGraphPattern = /gene-expression-atlas-okn/i;
    const queryTargetsGXA = gxaGraphPattern.test(finalQuery);

    // Inject FROM clauses if in federated mode with graphs
    if (mode === "federated" && graphs && Array.isArray(graphs) && graphs.length > 0) {
      finalQuery = injectFromClauses(finalQuery, graphs);
    }

    let endpoint = pack?.endpoint_mode.federated_endpoint ||
      process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
      "https://frink.apps.renci.org/federation/sparql";

    // Always run GXA template queries through the federated endpoint. Templates bind
    // log2fc/adj_p_value from both http://purl.org/okn/wobd/ and spokegenelab: for
    // compatibility; the direct GXA service only has wobd: predicates after the OKN-WOBD
    // RDF refresh. Federation remains the default path for timeouts and multi-graph queries.
    // NDE-intent queries (e.g. dataset_search) use the federated endpoint with FROM clauses
    // (already injected above); they are no longer routed to the NDE direct endpoint.

    // GXA queries can take 1–2 minutes (federation or direct); NDE can be slow for keyword search.
    const baseTimeout = options?.timeout_s ?? pack?.guardrails?.timeout_seconds ?? 25;
    const isGXA = queryTargetsGXA;
    const endpointIsNDE = !queryTargetsGXA && endpoint?.includes("nde");
    const federatedIncludesNDE = mode === "federated" && Array.isArray(graphs) && graphs.includes("nde");
    const timeout = isGXA
      ? Math.max(baseTimeout, 120)
      : endpointIsNDE || federatedIncludesNDE
        ? Math.max(baseTimeout, 60)
        : baseTimeout;

    // Optional preflight probes (skip for GXA queries — graph is large / slow to sample)
    let preflightResult = null;
    if (run_preflight !== false && pack?.schema_hints && !queryTargetsGXA) {
      try {
        preflightResult = await runPreflight(
          finalQuery,
          endpoint,
          pack.schema_hints.common_predicates,
          undefined // classes - could be extracted from query if needed
        );
      } catch (error: any) {
        // Preflight failures are non-fatal, just log
        console.warn("Preflight probe failed:", error.message);
      }
    }

    const runId = uuidv4();
    const queryFp = sparqlQueryFingerprint(finalQuery);

    let execResult = await executeSPARQL(finalQuery, endpoint, { timeout_s: timeout });
    const first_attempt_latency_ms = execResult.latency_ms;

    let repairResult: ReturnType<typeof attemptRepair> | null = null;
    let repairedQuery: string | null = null;
    let repair_candidate_valid_for_execute = false;
    let repair_retries_federation = false;
    let second_attempt_latency_ms: number | undefined;

    const repair_call_after_first_failure =
      !!(execResult.error && attempt_repair !== false);

    if (repair_call_after_first_failure) {
      repairResult = attemptRepair(finalQuery, execResult.error);
      if (repairResult.success && repairResult.repaired_query) {
        const repairValidation = validateSPARQL(repairResult.repaired_query, guardrails);
        repair_candidate_valid_for_execute = repairValidation.valid;
        if (repairValidation.valid) {
          repairedQuery = repairValidation.normalized_query || repairResult.repaired_query;
          if (mode === "federated" && graphs && Array.isArray(graphs) && graphs.length > 0) {
            repairedQuery = injectFromClauses(repairedQuery, graphs);
          }
          repair_retries_federation = true;
          execResult = await executeSPARQL(repairedQuery, endpoint, { timeout_s: timeout });
          second_attempt_latency_ms = execResult.latency_ms;
        }
      }
    }

    const runRecord = {
      run_id: runId,
      timestamp: new Date().toISOString(),
      user_message: "", // Will be filled by caller
      context_pack_id: pack_id || "default",
      context_pack_version: pack?.version || "0.0.0",
      lane: "raw" as const,
      executed_sparql: repairedQuery || finalQuery,
      repaired_sparql: repairedQuery || undefined,
      endpoint,
      graph_mode: (mode || "federated") as "federated" | "single_graph",
      graphs: graphs || [],
      from_clauses: mode === "federated" && graphs ? graphs.map((g: string) => `https://purl.org/okn/frink/kg/${g}`) : [],
      validation_decisions: {
        service_allowed: true, // Simplified for now
        limit_injected: !!validation.normalized_query,
        limit_value: validation.normalized_query ? undefined : undefined,
      },
      execution_metrics: {
        latency_ms: execResult.latency_ms,
        row_count: execResult.row_count,
        error: execResult.error,
      },
      repair_attempt: repairResult ? {
        attempted: true,
        success: repairResult.success,
        changes: repairResult.changes,
        repaired_query: repairResult.repaired_query,
      } : undefined,
      preflight_result: preflightResult || undefined,
    };

    runStore.save(runRecord);

    maybeLogTemplateSparqlExecute(template_task, {
      run_id: runId,
      pack_id: typeof pack_id === "string" ? pack_id : undefined,
      endpoint,
      timeout_s: timeout,
      mode: typeof mode === "string" ? mode : undefined,
      graphs: graphs ?? [],
      query_byte_length: new TextEncoder().encode(finalQuery).length,
      query_sha12: queryFp,
      first_attempt_latency_ms,
      second_attempt_latency_ms:
        typeof second_attempt_latency_ms === "number" ? second_attempt_latency_ms : undefined,
      outcome: execResult.error ? "failure" : "success",
      final_error_class: classifyExecuteError(execResult.error),
      repair_call_after_first_failure,
      repair_returned_candidate: !!(repairResult?.repaired_query),
      repair_candidate_valid_for_execute,
      repair_retries_federation,
      repair_changes: repairResult?.changes,
      row_count: execResult.row_count,
    });

    const response: Record<string, unknown> = {
      head: execResult.result.head,
      bindings: execResult.result.results.bindings,
      result: { head: execResult.result.head, results: execResult.result.results },
      stats: {
        row_count: execResult.row_count,
        latency_ms: execResult.latency_ms,
      },
      run_id: runId,
      endpoint_used: endpoint,
      repair_attempt: repairResult ? {
        attempted: true,
        success: repairResult.success,
        changes: repairResult.changes,
      } : undefined,
      preflight: preflightResult || undefined,
      error: execResult.error || undefined,
    };
    if (debug) {
      response.executed_query = repairedQuery || finalQuery;
    }
    return NextResponse.json(response);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Execution failed" },
      { status: 500 }
    );
  }
}

