import { NextResponse } from "next/server";

export async function POST(request: Request) {
    try {
        const { sparql, instruction } = await request.json();

        if (!sparql || !instruction) {
            return NextResponse.json(
                { error: "Missing sparql or instruction" },
                { status: 400 }
            );
        }

        // Use the same LLM endpoint pattern as other API routes
        const llmUrl = new URL("/api/tools/llm/complete", request.url).toString();

        const systemPrompt = `You are a SPARQL query assistant. The user has a SPARQL query and wants to modify it.

CRITICAL: Your response must ONLY contain the modified SPARQL query. Do not include:
- Explanations
- Comments about the changes
- Markdown formatting
- Code block markers
- Any text before or after the query

Your task:
1. Understand the user's instruction
2. Modify the SPARQL query accordingly
3. Return ONLY the complete modified SPARQL query
4. Ensure the query is syntactically valid

Common modifications:
- Adding/removing FILTER clauses
- Adding/modifying LIMIT
- Adding new variables to SELECT
- Adding OPTIONAL clauses for new fields
- Adding/removing FROM clauses
- Reordering or grouping results
- Adding GROUP BY and aggregation functions

IMPORTANT:
- Keep the query syntactically valid
- Preserve PREFIX declarations
- Preserve query structure
- If removing LIMIT, just delete the LIMIT line entirely
- If adding GROUP BY, make sure to use aggregation functions (GROUP_CONCAT, COUNT, etc.) for all non-grouped variables in SELECT
- CRITICAL: When adding GROUP BY, any FILTER statements that check BOUND(?variable) MUST remain at the WHERE clause level, NOT inside OPTIONAL blocks
- FILTER clauses should appear AFTER all graph patterns and BEFORE the closing brace of the WHERE clause
- Never create orphaned logical operators (|| or &&) that are not part of a complete FILTER expression
- Test your modifications mentally before returning the query
- If the instruction is unclear, make a reasonable interpretation

EXAMPLE of correct GROUP BY with BOUND filters:
WHERE {
  ?dataset a schema:Dataset .
  OPTIONAL { ?dataset schema:property1 ?prop1 }
  OPTIONAL { ?dataset schema:property2 ?prop2 }
  FILTER(BOUND(?prop1) || BOUND(?prop2))
}
GROUP BY ?dataset

INCORRECT (DO NOT DO THIS):
WHERE {
  ?dataset a schema:Dataset .
  OPTIONAL { ?dataset schema:property1 ?prop1 }
  OPTIONAL { ?dataset schema:property2 ?prop2 }
  || BOUND(?prop2))  # WRONG: orphaned operator
}
GROUP BY ?dataset`;

        const userPrompt = `Here is the SPARQL query:

${sparql}

Instruction: ${instruction}

Return only the modified SPARQL query with proper syntax:`;

        console.log("[SPARQL Modify] Modifying query with instruction:", instruction);

        const llmResponse = await fetch(llmUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider: "openai",
                model: "gpt-4o", // Use more capable model for complex SPARQL modifications
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: userPrompt },
                ],
                temperature: 0.1, // Very low temperature for precision
                max_tokens: 3000, // More tokens for complex queries
                use_shared: true,
            }),
        });

        if (!llmResponse.ok) {
            throw new Error(`LLM request failed: ${llmResponse.statusText}`);
        }

        const llmResult = await llmResponse.json();

        console.log("[SPARQL Modify] Full LLM result:", JSON.stringify(llmResult, null, 2));

        // The LLM complete endpoint returns { text, usage, provider_metadata }
        let modifiedQuery = llmResult.text || "";

        console.log("[SPARQL Modify] Raw LLM response length:", modifiedQuery.length);
        console.log("[SPARQL Modify] Raw LLM response (first 500 chars):", modifiedQuery.substring(0, 500));

        // Clean up the response - remove markdown code blocks if present
        // Handle both ```sparql and ``` blocks
        modifiedQuery = modifiedQuery
            .replace(/```sparql\n?/gi, "")
            .replace(/```sql\n?/gi, "")
            .replace(/```\n?/g, "")
            .trim();

        console.log("[SPARQL Modify] After cleanup, modified length:", modifiedQuery.length);
        console.log("[SPARQL Modify] Cleaned query (first 200 chars):", modifiedQuery.substring(0, 200));

        // Basic syntax validation - check for obvious errors
        const syntaxErrors: string[] = [];

        // Check for orphaned operators at line start (with any whitespace)
        if (/^\s*(\|\||&&)/m.test(modifiedQuery)) {
            syntaxErrors.push("Line starts with a logical operator (|| or &&)");
        }
        if (/(\|\||&&)\s*$/m.test(modifiedQuery)) {
            syntaxErrors.push("Line ends with a logical operator (|| or &&)");
        }

        // Specific check for the pattern we're seeing: lines starting with whitespace + "||" or "&&"
        // This catches "   || BOUND(?organism))" which is the error we're seeing
        const orphanedOperatorMatch = modifiedQuery.match(/^[ \t]+(\|\||&&)\s+\w+/m);
        if (orphanedOperatorMatch) {
            syntaxErrors.push(`Orphaned logical operator at start of line: "${orphanedOperatorMatch[0].trim()}"`);
        }

        // Check for operators followed by closing braces/parens (common error pattern)
        if (/(\|\||&&)\s*[}\)]/.test(modifiedQuery)) {
            syntaxErrors.push("Logical operator followed by closing brace/paren");
        }

        // Check for ") || BOUND" or "} || BOUND" patterns across lines
        if (/[}\)]\s*\n\s+(\|\||&&)\s+BOUND/m.test(modifiedQuery)) {
            syntaxErrors.push("BOUND filter appears to be orphaned after closing brace/paren");
        }

        // Check for mismatched braces
        const openBraces = (modifiedQuery.match(/\{/g) || []).length;
        const closeBraces = (modifiedQuery.match(/\}/g) || []).length;
        if (openBraces !== closeBraces) {
            syntaxErrors.push(`Mismatched braces: ${openBraces} open, ${closeBraces} close`);
        }

        // Check for mismatched parentheses
        const openParens = (modifiedQuery.match(/\(/g) || []).length;
        const closeParens = (modifiedQuery.match(/\)/g) || []).length;
        if (openParens !== closeParens) {
            syntaxErrors.push(`Mismatched parentheses: ${openParens} open, ${closeParens} close`);
        }

        // Check for incomplete FILTER statements
        if (/FILTER\s*\(\s*(\|\||&&)/.test(modifiedQuery)) {
            syntaxErrors.push("FILTER statement starts with logical operator");
        }

        // If there are syntax errors, return the original query with a warning
        if (syntaxErrors.length > 0) {
            console.warn("[SPARQL Modify] Syntax validation failed:", syntaxErrors.join(", "));
            console.warn("[SPARQL Modify] Invalid query was:", modifiedQuery);
            console.warn("[SPARQL Modify] Returning original query to prevent errors");
            modifiedQuery = sparql;
        } else {
            console.log("[SPARQL Modify] Syntax validation passed");
        }

        // Fallback: if the query is empty or too short, return the original
        if (modifiedQuery.length < 50) {
            console.warn("[SPARQL Modify] Modified query too short, returning original");
            modifiedQuery = sparql;
        }

        return NextResponse.json({
            original_query: sparql,
            instruction,
            modified_query: modifiedQuery,
            validation_errors: syntaxErrors.length > 0 ? syntaxErrors : undefined,
            fallback_used: syntaxErrors.length > 0,
        });
    } catch (error: any) {
        console.error("[SPARQL Modify] Error:", error);
        return NextResponse.json(
            { error: error.message || "Failed to modify query" },
            { status: 500 }
        );
    }
}
