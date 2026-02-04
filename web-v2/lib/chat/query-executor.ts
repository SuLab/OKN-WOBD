// Query execution service for all lanes

import type { Intent, SPARQLResult, ChatMessage, OntologyQueryState } from "@/types";
import { generateMessageId } from "./messages";

export interface QueryExecutionResult {
    message: ChatMessage;
    runId?: string;
}

export async function executeTemplateQuery(
    text: string,
    packId: string = "wobd",
    signal?: AbortSignal
): Promise<QueryExecutionResult> {
    // Step 1: Classify intent
    const intentResponse = await fetch("/api/tools/nl/intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, pack_id: packId }),
        signal,
    });

    if (!intentResponse.ok) {
        const error = await intentResponse.json();
        throw new Error(error.error || "Intent classification failed");
    }

    const intent: Intent = await intentResponse.json();

    // Step 2: Generate SPARQL from intent (template lane)
    const sparqlResponse = await fetch("/api/tools/nl/intent-to-sparql", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent, pack_id: packId }),
        signal,
    });

    if (!sparqlResponse.ok) {
        const error = await sparqlResponse.json();
        throw new Error(error.error || "SPARQL generation failed");
    }

    const { query: sparql } = await sparqlResponse.json();

    // Step 3: Execute SPARQL
    return executeSPARQLQuery(sparql, intent, packId, "template", signal);
}

export async function executeOpenQuery(
    text: string,
    packId: string = "wobd",
    useShared: boolean = true,
    signal?: AbortSignal
): Promise<QueryExecutionResult> {
    // Step 1: Generate SPARQL from natural language
    const openQueryResponse = await fetch("/api/tools/nl/open-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            text,
            pack_id: packId,
            use_shared: useShared,
        }),
        signal,
    });

    if (!openQueryResponse.ok) {
        const error = await openQueryResponse.json();
        throw new Error(error.error || "Open query generation failed");
    }

    const { query: sparql, original_query } = await openQueryResponse.json();

    // Step 2: Classify intent (for metadata)
    let intent: Intent | undefined;
    try {
        const intentResponse = await fetch("/api/tools/nl/intent", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, pack_id: packId }),
            signal,
        });
        if (intentResponse.ok) {
            intent = await intentResponse.json();
        }
    } catch (e) {
        // Intent classification is optional for open queries
    }

    // Step 3: Execute SPARQL
    return executeSPARQLQuery(sparql, intent, packId, "open", signal);
}

export async function executeRawSPARQL(
    sparql: string,
    packId: string = "wobd",
    signal?: AbortSignal
): Promise<QueryExecutionResult> {
    // Execute SPARQL directly
    console.log("[QueryExecutor] executeRawSPARQL called with query length:", sparql.length);
    console.log("[QueryExecutor] First 200 chars of query:", sparql.substring(0, 200));
    console.log("[QueryExecutor] Query contains MONDO_0011786:", sparql.includes("MONDO_0011786"));
    console.log("[QueryExecutor] Query contains MONDO_0004979:", sparql.includes("MONDO_0004979"));
    return executeSPARQLQuery(sparql, undefined, packId, "raw", signal);
}

async function executeSPARQLQuery(
    sparql: string,
    intent: Intent | undefined,
    packId: string,
    lane: "template" | "open" | "raw",
    signal?: AbortSignal
): Promise<QueryExecutionResult> {
    const executeResponse = await fetch("/api/tools/sparql/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            query: sparql,
            pack_id: packId,
            mode: intent?.graph_mode || "federated",
            graphs: intent?.graphs || [],
            attempt_repair: true,
            run_preflight: false, // Can be enabled later
        }),
        signal,
    });

    let result;
    try {
        result = await executeResponse.json();
    } catch (e) {
        // Failed to parse JSON response
        const errorText = await executeResponse.text().catch(() => "Unknown error");
        const errorMessage: ChatMessage = {
            id: generateMessageId(),
            role: "error",
            content: `Query execution failed: ${errorText}`,
            timestamp: new Date().toISOString(),
            lane,
            intent,
            sparql,
            error: errorText,
        };
        return { message: errorMessage };
    }

    const runId = result.run_id;

    if (!executeResponse.ok || result.error) {
        // Error response
        const errorMessage: ChatMessage = {
            id: generateMessageId(),
            role: "error",
            content: `Query execution failed: ${result.error || "Unknown error"}`,
            timestamp: new Date().toISOString(),
            lane,
            run_id: runId,
            intent,
            sparql,
            error: result.error,
        };

        return { message: errorMessage, runId };
    }

    // Success response - API returns { head, bindings } but we need { head, results: { bindings } }
    const results: SPARQLResult = {
        head: result.head,
        results: {
            bindings: result.bindings || [],
        },
    };

    const rowCount = result.stats?.row_count || 0;
    const latency = result.stats?.latency_ms || 0;

    console.log("[QueryExecutor] Query executed successfully, rowCount:", rowCount);
    console.log("[QueryExecutor] SPARQL that will be stored in message (length):", sparql.length);
    console.log("[QueryExecutor] SPARQL contains MONDO_0011786:", sparql.includes("MONDO_0011786"));
    console.log("[QueryExecutor] SPARQL contains MONDO_0004979:", sparql.includes("MONDO_0004979"));

    // Check if query has a LIMIT clause
    const hasLimit = sparql && /LIMIT\s+\d+/i.test(sparql);
    const limitMatch = sparql?.match(/LIMIT\s+(\d+)/i);
    const limitValue = limitMatch ? parseInt(limitMatch[1], 10) : null;

    // Extract ontology state from intent if present
    const ontologyState: OntologyQueryState | undefined = intent?.slots?.ontology_state;

    // If ontology-grounded query returned 0 results, try fallback text search
    // Only run fallback if we truly got 0 results (not if results exist from text matching in the ontology query)
    if (rowCount === 0 && intent?.ontology_workflow && ontologyState && lane === "template") {
        console.log("[QueryExecutor] Ontology query returned 0 results, attempting fallback text search...");
        const { buildNDEFallbackQuery } = await import("@/lib/ontology/templates");

        // Use detected entity term(s) instead of raw phrase for more precise text search
        // Priority: primary_entity term > identified_entities terms > grounded term labels > raw_phrase
        let searchTerms: string[] = [];

        // Try to get entity term from primary_entity
        if (ontologyState.debug_info?.primary_entity?.term) {
            searchTerms.push(ontologyState.debug_info.primary_entity.term);
        }

        // Or get terms from identified_entities
        if (searchTerms.length === 0 && ontologyState.debug_info?.identified_entities) {
            searchTerms = ontologyState.debug_info.identified_entities
                .map(e => e.term)
                .filter(Boolean);
        }

        // Or get labels from grounded terms
        if (searchTerms.length === 0 && ontologyState.grounded_mondo_terms?.length > 0) {
            searchTerms = ontologyState.grounded_mondo_terms
                .map(t => t.label)
                .filter(Boolean)
                .slice(0, 3); // Limit to top 3 labels
        }

        // Fallback to raw_phrase if no entity terms found
        if (searchTerms.length === 0) {
            const rawPhrase = ontologyState.raw_phrase || intent.slots?.keywords?.toString() || "";
            if (rawPhrase.trim().length > 0) {
                searchTerms = [rawPhrase];
            }
        }

        // Only retry if we have meaningful search terms
        if (searchTerms.length > 0) {
            try {
                // Use the first term as primary, others as candidate labels
                const primaryTerm = searchTerms[0];
                const candidateLabels = searchTerms.slice(1);
                const fallbackQuery = buildNDEFallbackQuery(primaryTerm, candidateLabels);

                // Execute fallback query
                const fallbackResponse = await fetch("/api/tools/sparql/execute", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        query: fallbackQuery,
                        pack_id: packId,
                        mode: intent?.graph_mode || "federated",
                        graphs: intent?.graphs || [],
                        attempt_repair: true,
                        run_preflight: false,
                    }),
                    signal,
                });

                const fallbackResult = await fallbackResponse.json();
                const fallbackRowCount = fallbackResult.stats?.row_count || 0;

                // If fallback found results, use those instead of the 0-results message
                if (fallbackRowCount > 0) {
                    console.log(`[QueryExecutor] Fallback text search found ${fallbackRowCount} results, returning fallback message (replacing 0-results message)`);
                    const fallbackResults: SPARQLResult = {
                        head: fallbackResult.head,
                        results: {
                            bindings: fallbackResult.bindings || [],
                        },
                    };

                    // Mark as fallback used
                    const fallbackOntologyState: OntologyQueryState = {
                        ...ontologyState,
                        fallback_used: true,
                    };

                    // Return fallback message INSTEAD of the 0-results message
                    // This prevents showing two messages (0 results + fallback results)
                    // IMPORTANT: This return statement prevents the code below from executing,
                    // so only ONE message is returned to the caller
                    const message: ChatMessage = {
                        id: generateMessageId(),
                        role: "assistant",
                        content: `Query executed successfully. Found ${fallbackRowCount} result${fallbackRowCount !== 1 ? "s" : ""} using text-based search (ontology matching returned no results).`,
                        timestamp: new Date().toISOString(),
                        lane,
                        run_id: fallbackResult.run_id,
                        intent,
                        sparql: fallbackQuery,
                        results: fallbackResults,
                        ontology_state: fallbackOntologyState,
                        metadata: {
                            row_count: fallbackRowCount,
                            latency_ms: (fallbackResult.stats?.latency_ms || 0) + latency,
                            repair_attempt: fallbackResult.repair_attempt,
                            preflight_result: fallbackResult.preflight,
                            limit_applied: hasLimit ? limitValue : undefined,
                            results_limited: hasLimit && limitValue && fallbackRowCount >= limitValue,
                        },
                    };

                    // Return fallback message - this replaces the 0-results message
                    // The caller will only receive this message, not the 0-results one
                    return { message, runId: fallbackResult.run_id };
                } else {
                    console.log("[QueryExecutor] Fallback text search also returned 0 results, will show original 0-results message");
                }
                // If fallback also returned 0 results, continue to show the original 0-results message
            } catch (fallbackError) {
                // If fallback fails, continue with original 0-result response
                console.warn("Fallback text search failed:", fallbackError);
            }
        }
    }

    // Format response message
    // Note: If fallback found results above, this code won't execute (early return)
    // This message is only shown if:
    // 1. No fallback was attempted (rowCount > 0, or not ontology workflow, etc.)
    // 2. Fallback was attempted but also returned 0 results
    let content = "";
    if (rowCount === 0) {
        content = "Query executed successfully but returned no results.";
    } else {
        content = `Query executed successfully. Found ${rowCount} result${rowCount !== 1 ? "s" : ""}.`;
    }

    const message: ChatMessage = {
        id: generateMessageId(),
        role: "assistant",
        content,
        timestamp: new Date().toISOString(),
        lane,
        run_id: runId,
        intent,
        sparql,
        results,
        ontology_state: ontologyState,
        metadata: {
            row_count: rowCount,
            latency_ms: latency,
            repair_attempt: result.repair_attempt,
            preflight_result: result.preflight,
            limit_applied: hasLimit ? limitValue : undefined,
            results_limited: hasLimit && limitValue && rowCount >= limitValue,
        },
    };

    return { message, runId };
}

