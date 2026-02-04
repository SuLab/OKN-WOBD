// LLM-based candidate label generation for ontology-grounded queries
// Generates clinical disease names from colloquial phrases

interface CandidateLabelsResponse {
  entity_type: string;
  raw_phrase: string;
  candidate_labels: string[];
}

/**
 * Generate candidate disease/condition labels from a colloquial phrase using LLM
 * Returns max 10 labels, strings only (no IRIs, CURIEs, SPARQL)
 */
export async function generateCandidateLabels(
  text: string,
  entityType: string = "disease",
  llmUrl?: string
): Promise<string[]> {
  const systemPrompt = `You are a medical terminology expert. Convert colloquial disease/condition phrases into clinical disease names.

Rules:
- Output ONLY valid JSON, no other text
- Maximum 10 candidate labels
- Strings only (no IRIs, CURIEs, SPARQL, or ontology names)
- Use standard medical terminology
- Return JSON in this exact format:
{
  "entity_type": "${entityType}",
  "raw_phrase": "${text}",
  "candidate_labels": ["label1", "label2", ...]
}`;

  const userPrompt = `Convert this phrase to clinical disease names: "${text}"`;

  try {
    // Use shared OpenAI API key via the LLM proxy
    // Use provided URL or construct from environment
    const endpointUrl = llmUrl || (typeof window === "undefined" && process.env.NEXT_PUBLIC_APP_URL
      ? `${process.env.NEXT_PUBLIC_APP_URL}/api/tools/llm/complete`
      : "/api/tools/llm/complete");

    // Use shared key if available (server-side), otherwise requires session_id for BYOK
    const useShared = typeof process !== "undefined" && !!process.env.ANTHROPIC_SHARED_API_KEY;

    const response = await fetch(endpointUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: "anthropic",
        model: "claude-sonnet-4-5",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.3, // Lower temperature for more consistent results
        max_tokens: 500,
        use_shared: useShared,
        // session_id can be passed if not using shared key
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Unknown error" }));
      throw new Error(error.error || `LLM call failed: ${response.status}`);
    }

    const result = await response.json();
    const text = result.text?.trim() || "";

    // Parse JSON response
    let parsed: CandidateLabelsResponse;
    try {
      // Try to extract JSON from markdown code blocks if present
      const jsonMatch = text.match(/```(?:json)?\s*(\{[\s\S]*\})\s*```/) ||
        text.match(/(\{[\s\S]*\})/);
      const jsonText = jsonMatch ? jsonMatch[1] : text;
      parsed = JSON.parse(jsonText);
    } catch (_parseError) {
      throw new Error(`Failed to parse LLM response as JSON: ${text.substring(0, 200)}`);
    }

    // Validate response structure
    if (!Array.isArray(parsed.candidate_labels)) {
      throw new Error("LLM response missing candidate_labels array");
    }

    // Enforce max 10 labels
    const labels = parsed.candidate_labels
      .slice(0, 10)
      .filter((label: any): label is string =>
        typeof label === "string" &&
        label.trim().length > 0 &&
        !label.includes("http://") && // No IRIs
        !label.includes("MONDO:") && // No CURIEs
        !label.toUpperCase().includes("SELECT") // No SPARQL
      )
      .map((label: string) => label.trim());

    if (labels.length === 0) {
      throw new Error("No valid candidate labels generated");
    }

    return labels;
  } catch (error: any) {
    // If LLM fails, return empty array - caller will handle fallback
    console.error("Candidate label generation failed:", error);
    throw error;
  }
}

