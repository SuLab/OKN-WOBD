import { NextResponse } from "next/server";
import { executeSPARQL, injectFromClauses, removeFromClauses } from "@/lib/sparql/executor";
import { validateSPARQL } from "@/lib/sparql/validator";
import { loadContextPack } from "@/lib/context-packs/loader";
import { runStore } from "@/lib/runs/store";
import { attemptRepair } from "@/lib/sparql/repair";
import { runPreflight } from "@/lib/sparql/preflight";

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
    const { query, pack_id, mode, graphs, options, run_preflight, attempt_repair, debug } = body;

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

    // Inject FROM clauses if in federated mode with graphs
    if (mode === "federated" && graphs && Array.isArray(graphs) && graphs.length > 0) {
      finalQuery = injectFromClauses(finalQuery, graphs);
    }

    // Determine endpoint - check if query targets GXA graph and use direct endpoint
    let endpoint = pack?.endpoint_mode.federated_endpoint ||
      process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
      "https://frink.apps.renci.org/federation/sparql";

    // If query targets gene-expression-atlas-okn graph, use direct endpoint
    const gxaGraphPattern = /gene-expression-atlas-okn/i;
    const hasGXAGraph = gxaGraphPattern.test(finalQuery) ||
      (graphs && Array.isArray(graphs) && graphs.some((g: string) => gxaGraphPattern.test(g)));

    if (hasGXAGraph && pack?.endpoint_mode.direct_endpoints?.["gene-expression-atlas-okn"]) {
      endpoint = pack.endpoint_mode.direct_endpoints["gene-expression-atlas-okn"];
      // Remove all FROM clauses when querying direct endpoint (default graph is the GXA graph)
      finalQuery = removeFromClauses(finalQuery);
    }

    // GXA direct endpoint can take 1–2 minutes; use a longer timeout when routing to it
    const baseTimeout = options?.timeout_s ?? pack?.guardrails?.timeout_seconds ?? 25;
    const timeout = hasGXAGraph && endpoint?.includes("gene-expression-atlas-okn")
      ? Math.max(baseTimeout, 120)
      : baseTimeout;

    // Optional preflight probes (skip for GXA direct endpoint, which can be slow and
    // has been flaky with small sample queries)
    let preflightResult = null;
    if (run_preflight !== false && pack?.schema_hints && !hasGXAGraph) {
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

    // Execute
    let execResult = await executeSPARQL(finalQuery, endpoint, { timeout_s: timeout });

    // Attempt repair if execution failed and repair is enabled
    let repairResult = null;
    let repairedQuery = null;
    if (execResult.error && (attempt_repair !== false)) {
      repairResult = attemptRepair(finalQuery, execResult.error);
      if (repairResult.success && repairResult.repaired_query) {
        // Validate repaired query
        const repairValidation = validateSPARQL(repairResult.repaired_query, guardrails);
        if (repairValidation.valid) {
          repairedQuery = repairValidation.normalized_query || repairResult.repaired_query;
          // Re-inject FROM clauses if needed
          if (mode === "federated" && graphs && Array.isArray(graphs) && graphs.length > 0) {
            repairedQuery = injectFromClauses(repairedQuery, graphs);
          }
          // Retry execution with repaired query
          execResult = await executeSPARQL(repairedQuery, endpoint, { timeout_s: timeout });
        }
      }
    }

    // Create run record
    const runId = uuidv4();
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

