import { NextResponse } from "next/server";

export async function POST(request: Request) {
    try {
        const { sparql } = await request.json();

        if (!sparql) {
            return NextResponse.json(
                { error: "Missing sparql parameter" },
                { status: 400 }
            );
        }

        // Use the same LLM endpoint pattern as other API routes
        const llmUrl = new URL("/api/tools/llm/complete", request.url).toString();

        const systemPrompt = `You are a SPARQL query explainer. Your task is to read a SPARQL query and explain what it does in simple, plain English.

Your explanation should:
1. Be concise (1-2 sentences)
2. Focus on WHAT the query retrieves, not HOW
3. Avoid technical jargon
4. Be understandable to someone who doesn't know SPARQL

Examples:
- "Retrieves all datasets about diabetes from the NDE graph"
- "Finds datasets related to influenza, including disease names and descriptions"
- "Searches for experiments where the gene DUSP2 is upregulated"

Do NOT include:
- Technical details about FILTER clauses, OPTIONAL blocks, etc.
- The word "SPARQL" or "query"
- Prefixes or namespaces
- Implementation details`;

        const userPrompt = `Explain this query in plain English:

${sparql}

Plain English explanation:`;

        const llmResponse = await fetch(llmUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider: "openai",
                model: "gpt-4o-mini",
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: userPrompt },
                ],
                temperature: 0.3,
                max_tokens: 150,
                use_shared: true,
            }),
        });

        if (!llmResponse.ok) {
            throw new Error(`LLM request failed: ${llmResponse.statusText}`);
        }

        const llmResult = await llmResponse.json();
        const summary = (llmResult.text || "").trim();

        return NextResponse.json({
            summary,
        });
    } catch (error: any) {
        console.error("[SPARQL Summarize] Error:", error);
        return NextResponse.json(
            { error: error.message || "Failed to summarize query" },
            { status: 500 }
        );
    }
}
