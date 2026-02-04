import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";
import { validateSPARQL } from "@/lib/sparql/validator";
import { proxyLLMCall } from "@/lib/llm/proxy";
import { checkBudget, recordUsage } from "@/lib/llm/budget";
import { getBYOKKey } from "@/lib/keys/manager";
import type { LLMRequest } from "@/lib/llm/providers/types";

// Lane B: LLM-generated SPARQL - LLM generates SPARQL directly from natural language
export async function POST(request: Request) {
    try {
        const body = await request.json();
        const { text, pack_id, session_id, use_shared, provider, model, graphs } = body;

        if (!text || typeof text !== "string") {
            return NextResponse.json(
                { error: "Missing or invalid 'text' parameter" },
                { status: 400 }
            );
        }

        const pack = pack_id ? loadContextPack(pack_id) : loadContextPack("wobd");
        if (!pack) {
            return NextResponse.json(
                { error: `Context pack not found: ${pack_id || "wobd"}` },
                { status: 404 }
            );
        }

        // Check if LLM-generated SPARQL (Lane B) is allowed
        if (!pack.guardrails.allow_open_nl2sparql) {
            return NextResponse.json(
                { error: "LLM-generated SPARQL (Lane B) is disabled for this context pack" },
                { status: 403 }
            );
        }

        // Determine API key and provider
        const llmProvider = provider || "anthropic";
        const llmModel = model || (llmProvider === "openai" ? "gpt-4o-mini" : "claude-sonnet-4-5");

        let apiKey: string | null = null;

        if (use_shared && llmProvider === "openai") {
            const budgetCheck = checkBudget();
            if (!budgetCheck.allowed) {
                return NextResponse.json(
                    { error: budgetCheck.error || "Shared budget exceeded", code: "SHARED_BUDGET_EXCEEDED" },
                    { status: 402 }
                );
            }
            apiKey = process.env.OPENAI_SHARED_API_KEY || null;
            if (!apiKey) {
                return NextResponse.json(
                    { error: "Shared OpenAI API key not configured" },
                    { status: 500 }
                );
            }
        } else {
            if (!session_id) {
                return NextResponse.json(
                    { error: "session_id required for BYOK" },
                    { status: 400 }
                );
            }
            apiKey = getBYOKKey(llmProvider as any, session_id);
            if (!apiKey) {
                return NextResponse.json(
                    { error: `No API key found for provider ${llmProvider}` },
                    { status: 401 }
                );
            }
        }

        // Build system prompt with context pack information
        const systemPrompt = buildSystemPrompt(pack, graphs || pack.graphs.default_shortnames);

        // Build user prompt
        const userPrompt = `Generate a SPARQL query for the following question:\n\n${text}\n\nReturn ONLY the SPARQL query, no explanations or markdown formatting.`;

        // Make LLM call
        const llmRequest: LLMRequest = {
            provider: llmProvider as any,
            model: llmModel,
            messages: [
                { role: "system", content: systemPrompt },
                { role: "user", content: userPrompt },
            ],
            temperature: 0.1, // Low temperature for more deterministic SPARQL
            max_tokens: 2000,
        };

        const llmResponse = await proxyLLMCall(llmRequest, apiKey);

        // Record usage if using shared key
        if (use_shared && llmProvider === "openai") {
            recordUsage(llmModel, llmResponse.usage.input_tokens, llmResponse.usage.output_tokens, "open");
        }

        // Extract SPARQL from response (remove markdown code blocks if present)
        let sparqlQuery = llmResponse.text.trim();
        sparqlQuery = sparqlQuery.replace(/^```sparql\n?/i, "").replace(/^```\n?/i, "").replace(/\n?```$/i, "").trim();

        // Validate generated SPARQL
        const validation = validateSPARQL(sparqlQuery, pack.guardrails);

        if (!validation.valid) {
            return NextResponse.json(
                {
                    error: "Generated SPARQL query failed validation",
                    validation_errors: validation.errors,
                    warnings: validation.warnings,
                    generated_query: sparqlQuery,
                },
                { status: 400 }
            );
        }

        // Use normalized query if available (e.g., LIMIT was injected)
        const finalQuery = validation.normalized_query || sparqlQuery;

        return NextResponse.json({
            query: finalQuery,
            original_query: sparqlQuery,
            validation: {
                valid: true,
                warnings: validation.warnings,
                limit_injected: !!validation.normalized_query,
            },
            usage: llmResponse.usage,
            provider_metadata: llmResponse.provider_metadata,
        });
    } catch (error: any) {
        return NextResponse.json(
            { error: error.message || "Open query generation failed" },
            { status: 500 }
        );
    }
}

function buildSystemPrompt(pack: any, graphs: string[]): string {
    const lines: string[] = [];

    lines.push("You are a SPARQL query generator for biomedical knowledge graphs.");
    lines.push("Generate valid SPARQL SELECT or ASK queries only.");
    lines.push("");

    // Prefixes
    lines.push("Available prefixes:");
    for (const [prefix, uri] of Object.entries(pack.prefixes)) {
        lines.push(`  PREFIX ${prefix}: <${uri}>`);
    }
    lines.push("");

    // Graphs
    if (graphs && graphs.length > 0) {
        lines.push("Available graphs (use FROM clauses to scope queries):");
        for (const shortname of graphs) {
            lines.push(`  FROM <https://purl.org/okn/frink/kg/${shortname}>`);
        }
        lines.push("Note: If no FROM clauses are specified, the query will run over all graphs.");
        lines.push("");
    }

    // Example queries
    if (pack.schema_hints?.example_queries && pack.schema_hints.example_queries.length > 0) {
        lines.push("Example queries:");
        for (const example of pack.schema_hints.example_queries) {
            lines.push(example);
        }
        lines.push("");
    }

    // Common predicates
    if (pack.schema_hints?.common_predicates && pack.schema_hints.common_predicates.length > 0) {
        lines.push("Common predicates to use:");
        for (const pred of pack.schema_hints.common_predicates) {
            lines.push(`  - ${pred}`);
        }
        lines.push("");
    }

    // Guardrails
    lines.push("Constraints:");
    lines.push(`  - Maximum LIMIT: ${pack.guardrails.max_limit}`);
    lines.push("  - Forbidden operations: INSERT, DELETE, LOAD, CLEAR, DROP, CREATE, MOVE, COPY, ADD");
    lines.push("  - Always include a LIMIT clause");
    lines.push("  - Use SELECT or ASK queries only");
    lines.push("");

    lines.push("Generate clean, valid SPARQL queries that follow these guidelines.");

    return lines.join("\n");
}

