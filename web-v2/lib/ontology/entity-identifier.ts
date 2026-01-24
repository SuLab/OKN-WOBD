// LLM-based entity identification for ontology-grounded queries
// Identifies entities from user phrase and maps them to appropriate ontologies

import { formatOntologyMappingForLLM } from "./ontology-mapping";

export interface IdentifiedEntity {
  term: string;
  domain: string; // e.g., "disease", "species", "drug"
  ontology: string; // e.g., "MONDO", "NCBITaxon", "CHEBI"
  confidence?: number;
}

export interface EntityIdentificationResponse {
  entities: IdentifiedEntity[];
  primary_entity?: IdentifiedEntity; // The main entity if multiple found
}

/**
 * Identify entities from user phrase using LLM
 * Returns entities with their domain/topic and ontology mapping
 */
export async function identifyEntities(
  text: string,
  llmUrl?: string
): Promise<EntityIdentificationResponse> {
  const ontologyMapping = formatOntologyMappingForLLM();

  const systemPrompt = `You are a biomedical entity identification expert. Identify entity terms from user queries and map them to appropriate ontologies.

Available ontology mappings:
${ontologyMapping}

Gene Expression Concepts:
- "upregulated", "up-regulation", "up regulation", "increased expression", "overexpressed" → gene_expression (upregulation)
- "downregulated", "down-regulation", "down regulation", "decreased expression", "underexpressed" → gene_expression (downregulation)
- "differentially expressed", "differential expression", "expression change" → gene_expression (differential)
- "expression", "gene expression", "transcription" (when referring to gene activity) → gene_expression

Gene Symbol Recognition:
- Capitalized short names (e.g., "Dusp2", "TP53", "BRCA1", "EGFR") are likely gene symbols
- Gene symbols are typically 2-10 characters, may include numbers
- Common patterns: all caps (TP53), mixed case (Dusp2), or specific capitalization (BRCA1)
- Gene symbols often appear in context of "expression", "upregulated", "downregulated", "knockout", etc.

Gene Name Recognition:
- Descriptive phrases that describe gene function or protein products are gene names
- Examples: "dual specificity phosphatase 2", "tumor protein p53", "epidermal growth factor receptor", "cyclin-dependent kinase"
- Gene names are longer, multi-word descriptive phrases (typically 3+ words or 15+ characters)
- Common patterns: contain words like "phosphatase", "protein", "receptor", "factor", "enzyme", "kinase", "transcription", "binding", "domain", "subunit"
- Gene names often appear in context of "expression", "upregulated", "downregulated", "experiments", "where"
- When you see a descriptive phrase like "dual specificity phosphatase 2" in a query about experiments or expression, it is a GENE NAME, not a disease or other entity type
- For gene names, use domain "gene" and ontology "HGNC" (same as gene symbols)

Rules:
- Output ONLY valid JSON, no other text
- Identify 1-5 key entities from the user phrase
- For each entity, determine its domain/topic (disease, species, drug, gene, gene_expression, etc.)
- Map each entity to the appropriate ontology using the mapping above
- For gene symbols (short codes like "Dusp2", "TP53"), use domain "gene" and ontology "HGNC"
- For gene names (descriptive phrases like "dual specificity phosphatase 2"), use domain "gene" and ontology "HGNC"
- For gene expression concepts, use domain "gene_expression" and ontology "NONE"
- For drugs/medications, use domain "drug" or "medication" and ontology "Wikidata" (we prefer Wikidata for drugs)
- IMPORTANT: When a descriptive phrase appears in a query about experiments, expression, or upregulation/downregulation, it is likely a gene name and should be classified as domain "gene"
- IMPORTANT: Some terms can have MULTIPLE entity types. For example:
  * "influenza" can be BOTH a disease (domain: "disease", ontology: "MONDO") AND an organism/pathogen (domain: "species", ontology: "NCBITaxon")
  * "malaria" can be BOTH a disease (domain: "disease", ontology: "MONDO") AND an organism/pathogen (domain: "species", ontology: "NCBITaxon")
  * When you identify such dual-nature terms, include BOTH entity types as separate entries in the entities array
- Return JSON in this exact format:
{
  "entities": [
    {
      "term": "entity term",
      "domain": "gene",
      "ontology": "HGNC",
      "confidence": 0.9
    },
    {
      "term": "upregulated",
      "domain": "gene_expression",
      "ontology": "NONE",
      "confidence": 0.95
    }
  ],
  "primary_entity": {
    "term": "main entity term",
    "domain": "gene",
    "ontology": "HGNC",
    "confidence": 0.95
  }
}

- "term" should be the exact phrase from the user query or a normalized version
- "domain" must match one of the domains in the mapping
- "ontology" must match the ontology for that domain (use "NONE" for gene_expression)
- "confidence" is optional (0.0-1.0)
- "primary_entity" is the most important entity if multiple are found
- When both a gene symbol and gene expression concept are present, prioritize the gene as primary_entity`;

  const userPrompt = `Identify entities in this query: "${text}"`;

  try {
    const endpointUrl =
      llmUrl ||
      (typeof window === "undefined" && process.env.NEXT_PUBLIC_APP_URL
        ? `${process.env.NEXT_PUBLIC_APP_URL}/api/tools/llm/complete`
        : "/api/tools/llm/complete");

    // Use shared key if available (server-side), otherwise requires session_id for BYOK
    // Note: On server-side, we check env vars; session_id can be passed for BYOK
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
        temperature: 0.3,
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
    const textResponse = result.text?.trim() || "";

    // Parse JSON response
    let parsed: EntityIdentificationResponse;
    try {
      // Try to extract JSON from markdown code blocks if present
      const jsonMatch =
        textResponse.match(/```(?:json)?\s*(\{[\s\S]*\})\s*```/) ||
        textResponse.match(/(\{[\s\S]*\})/);
      const jsonText = jsonMatch ? jsonMatch[1] : textResponse;
      parsed = JSON.parse(jsonText);
    } catch (_parseError) {
      throw new Error(
        `Failed to parse LLM response as JSON: ${textResponse.substring(0, 200)}`
      );
    }

    // Validate response structure
    if (!Array.isArray(parsed.entities) || parsed.entities.length === 0) {
      console.error(`[EntityIdentifier] LLM returned empty entities array. Full response:`, textResponse);
      console.error(`[EntityIdentifier] Parsed structure:`, JSON.stringify(parsed, null, 2));
      throw new Error("LLM response missing or empty entities array");
    }

    // Validate each entity has required fields
    const validEntities = parsed.entities.filter(
      (e: any) =>
        typeof e.term === "string" &&
        e.term.trim().length > 0 &&
        typeof e.domain === "string" &&
        typeof e.ontology === "string"
    );

    if (validEntities.length === 0) {
      throw new Error("No valid entities identified");
    }

    // Set primary_entity if not provided (use first entity)
    if (!parsed.primary_entity && validEntities.length > 0) {
      parsed.primary_entity = validEntities[0];
    }

    return {
      entities: validEntities,
      primary_entity: parsed.primary_entity || validEntities[0],
    };
  } catch (error: any) {
    console.error("Entity identification failed:", error);
    throw error;
  }
}

/**
 * Generate alternative names for an entity when OLS grounding fails
 * Only called as a fallback when initial OLS search returns no results
 */
export async function generateAlternativeNames(
  entity: IdentifiedEntity,
  llmUrl?: string
): Promise<string[]> {
  const systemPrompt = `You are a biomedical terminology expert. Generate alternative names for a biomedical entity.

Rules:
- Output ONLY valid JSON, no other text
- Generate 3-5 alternative names/synonyms for the entity
- Focus on names related to the domain: ${entity.domain}
- Use standard medical/scientific terminology
- Return JSON in this exact format:
{
  "alternatives": ["name1", "name2", "name3", "name4", "name5"]
}

- Maximum 5 alternatives
- Strings only (no IRIs, CURIEs, or ontology names)
- Should be terms that might appear in ontologies`;

  const userPrompt = `Generate 3-5 alternative names for "${entity.term}" in the context of ${entity.domain} (ontology: ${entity.ontology})`;

  try {
    const endpointUrl =
      llmUrl ||
      (typeof window === "undefined" && process.env.NEXT_PUBLIC_APP_URL
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
        temperature: 0.3,
        max_tokens: 300,
        use_shared: useShared,
        // session_id can be passed if not using shared key
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Unknown error" }));
      throw new Error(error.error || `LLM call failed: ${response.status}`);
    }

    const result = await response.json();
    const textResponse = result.text?.trim() || "";

    // Parse JSON response
    let parsed: { alternatives?: string[] };
    try {
      const jsonMatch =
        textResponse.match(/```(?:json)?\s*(\{[\s\S]*\})\s*```/) ||
        textResponse.match(/(\{[\s\S]*\})/);
      const jsonText = jsonMatch ? jsonMatch[1] : textResponse;
      parsed = JSON.parse(jsonText);
    } catch (_parseError) {
      throw new Error(
        `Failed to parse LLM response as JSON: ${textResponse.substring(0, 200)}`
      );
    }

    // Validate and clean alternatives
    if (!Array.isArray(parsed.alternatives)) {
      throw new Error("LLM response missing alternatives array");
    }

    const alternatives = parsed.alternatives
      .slice(0, 5)
      .filter(
        (alt: any): alt is string =>
          typeof alt === "string" &&
          alt.trim().length > 0 &&
          !alt.includes("http://") &&
          !alt.includes("MONDO:") &&
          !alt.toUpperCase().includes("SELECT")
      )
      .map((alt: string) => alt.trim());

    if (alternatives.length === 0) {
      throw new Error("No valid alternatives generated");
    }

    return alternatives;
  } catch (error: any) {
    console.error("Alternative name generation failed:", error);
    throw error;
  }
}


