import type { ContextPack, GraphMetadata } from "@/lib/context-packs/types";
import type { QueryPlan, QueryStep, Intent } from "@/types";
import { generateMessageId } from "@/lib/chat/messages";

const CROSS_GRAPH_PATTERNS = `
Common multi-graph query patterns:

1. Drug → Diseases (with MONDO from Wikidata) → Datasets
   - Step 1: Query wikidata for drug's disease indications (wdt:P2175) with MONDO IDs (wdt:P5270/wdtn:P5270)
   - Step 2: Query nde for datasets with those MONDO IRIs

2. Gene → Diseases → Datasets
   - Step 1: Query wikidata for gene-disease associations (wdt:P2293) with MONDO mappings
   - Step 2: Query nde for datasets with those MONDO IRIs

3. Disease Name → MONDO → Datasets
   - Step 1: Resolve disease to MONDO in ubergraph
   - Step 2: Query nde with MONDO IRI
`;

export async function planMultiHopQuery(
    userQuery: string,
    contextPack: ContextPack,
    llmEndpoint: string,
    sessionId?: string
): Promise<QueryPlan> {
    const graphs = contextPack.graphs_metadata || [];

    const systemPrompt = buildPlannerPrompt(graphs);
    const userPrompt = `User query: "${userQuery}"\n\nGenerate a multi-step query plan as JSON.`;

    // Default to shared key (use_shared: true) - the server will check for ANTHROPIC_SHARED_API_KEY
    // If shared key is not configured, the server will return an error
    // For BYOK, users can set up their API key via the session system
    const response = await fetch(llmEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            provider: "anthropic",
            model: "claude-sonnet-4-5",
            messages: [
                { role: "system", content: systemPrompt },
                { role: "user", content: userPrompt },
            ],
            temperature: 0.2,
            max_tokens: 2000,
            use_shared: true, // Use shared key by default
            // session_id is not needed when use_shared is true
        }),
    });

    if (!response.ok) {
        throw new Error(`LLM request failed: ${response.statusText}`);
    }

    const result = await response.json();

    // Clean up the LLM response - remove markdown code fences if present
    let cleanedText = result.text.trim();
    if (cleanedText.startsWith("```json")) {
        cleanedText = cleanedText.replace(/^```json\s*\n?/g, "").replace(/\n?```\s*$/g, "");
    } else if (cleanedText.startsWith("```")) {
        cleanedText = cleanedText.replace(/^```\s*\n?/g, "").replace(/\n?```\s*$/g, "");
    }

    console.log("[Planner] Cleaned LLM response:", cleanedText.substring(0, 200));

    // Try to extract JSON from the response if it's embedded in text
    let planJson;
    try {
        planJson = JSON.parse(cleanedText);
    } catch (parseError) {
        // Try to find JSON object in the response
        const jsonMatch = cleanedText.match(/\{[\s\S]*"steps"[\s\S]*\}/);
        if (jsonMatch) {
            console.log("[Planner] Extracted JSON from response:", jsonMatch[0].substring(0, 200));
            try {
                planJson = JSON.parse(jsonMatch[0]);
            } catch (extractError) {
                console.error("[Planner] Failed to parse extracted JSON:", extractError);
                throw new Error(`LLM response is not valid JSON. Response started with: "${cleanedText.substring(0, 100)}"`);
            }
        } else {
            console.error("[Planner] No JSON object found in response");
            throw new Error(`LLM response is not valid JSON. Response started with: "${cleanedText.substring(0, 100)}"`);
        }
    }

    console.log("[Planner] Parsed plan JSON:", JSON.stringify(planJson, null, 2));

    // Convert LLM output to QueryPlan
    const plan: QueryPlan = {
        id: generateMessageId(),
        steps: planJson.steps.map((s: any, idx: number) => ({
            id: s.id || `step${idx + 1}`,
            description: s.description,
            intent: {
                lane: s.task === "raw_sparql" ? "raw" as const : "template" as const,
                task: s.task,
                context_pack: contextPack.id,
                graph_mode: "federated" as const,
                graphs: s.target_graphs,
                slots: s.slots || {},
                confidence: 0.9,
                notes: "",
            },
            target_graphs: s.target_graphs,
            depends_on: s.depends_on || [],
            uses_results_from: s.uses_results_from,
            status: "pending" as const,
            sparql: s.sparql, // Add raw SPARQL if provided
        })),
        original_query: userQuery,
        created_at: Date.now(),
        graph_routing_rationale: planJson.rationale,
    };

    return plan;
}

function buildPlannerPrompt(graphs: GraphMetadata[]): string {
    const graphDescriptions = graphs.map(g => `
- ${g.id}: ${g.description}
  Good for: ${g.good_for.join(", ")}
  ${g.notable_relationships ? `Relationships: ${g.notable_relationships.join("; ")}` : ""}
  ${g.provides_ontologies ? `Provides: ${g.provides_ontologies.join(", ")}` : ""}
  ${g.uses_ontologies ? `Uses: ${g.uses_ontologies.join(", ")}` : ""}
  `).join("\n");

    return `You are a query planner for biomedical knowledge graphs.

Available graphs:
${graphDescriptions}

${CROSS_GRAPH_PATTERNS}

Generate a multi-step query plan as JSON:
{
  "steps": [
    {
      "id": "step1",
      "description": "Resolve drug 'aspirin' to Wikidata identifier",
      "task": "entity_resolution",
      "target_graphs": ["wikidata"],
      "depends_on": [],
      "slots": {
        "entity_type": "drug",
        "entity_name": "aspirin",
        "target_ontology": "Wikidata"
      }
    },
    {
      "id": "step2",
      "description": "Find diseases treated by aspirin in Wikidata with MONDO IDs",
      "task": "raw_sparql",
      "target_graphs": ["wikidata"],
      "depends_on": ["step1"],
      "uses_results_from": "step1",
      "sparql": "PREFIX wd: <http://www.wikidata.org/entity/>\\nPREFIX wdt: <http://www.wikidata.org/prop/direct/>\\nPREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/>\\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\\n\\nSELECT DISTINCT ?disease ?diseaseLabel ?mondo_id ?mondoIRI\\nFROM <https://purl.org/okn/frink/kg/wikidata>\\nWHERE {\\n  VALUES ?drug { {{step1.drug_iris}} }\\n  ?drug wdt:P2175 ?disease .\\n  ?disease rdfs:label ?diseaseLabel .\\n  FILTER(LANG(?diseaseLabel) = \\"en\\")\\n  OPTIONAL { ?disease wdt:P5270 ?mondo_id . }\\n  OPTIONAL { ?disease wdtn:P5270 ?mondoIRI . }\\n}\\nLIMIT 50"
    },
    {
      "id": "step3",
      "description": "Query NDE datasets for MONDO diseases from step2",
      "task": "dataset_search",
      "target_graphs": ["nde"],
      "depends_on": ["step2"],
      "uses_results_from": "step2",
      "slots": {
        "health_conditions": "{{step2.disease_iris}}"
      }
    }
  ],
  "rationale": "Query requires: 1) resolving drug name to Wikidata IRI, 2) finding diseases treated by drug in Wikidata with MONDO IDs (wdt:P5270), 3) querying NDE for datasets with those MONDO diseases"
}

ENTITY RESOLUTION STEPS:
- If the query mentions entities by NAME (not IRI), add an entity_resolution step FIRST
- Entity resolution steps should have:
  - task: "entity_resolution"
  - target_graphs: ["wikidata"] for drugs/genes, ["ubergraph"] for diseases
  - slots: { entity_type: "drug"|"gene"|"disease", entity_name: "Name from query", target_ontology: "Wikidata"|"MONDO" }
  - description: "Resolve [entity_type] '[entity_name]' to [target_ontology] identifier"
- Subsequent steps should depend on the entity_resolution step and use {{stepN.entity_iris}} or {{stepN.drug_iris}} etc.

Rules:
- For custom queries, use task "raw_sparql" and provide complete SPARQL in "sparql" field
- Use template syntax {{stepN.field}} for result passing (will be replaced at runtime)
- For known tasks like "dataset_search", use task name and provide slots
- Prefer raw_sparql for Wikidata queries, use dataset_search for NDE queries
- Include complete SPARQL with all necessary prefixes
- Escape newlines in SPARQL as \\n
- ALWAYS add entity_resolution step if query mentions drugs, genes, or diseases by name

WIKIDATA PROPERTIES (use correct direction and property!):
- wdt:P2175 (medical condition treated) - Use: ?drug wdt:P2175 ?disease (drug treats disease)
- wdt:P2176 (drug used for treatment) - INVERSE - Use: ?disease wdt:P2176 ?drug (disease is treated by drug)
- wdt:P5270 (MONDO ID) - Use for MONDO mapping: ?disease wdt:P5270 ?mondo_id (returns literal like "0005015")
- wdtn:P5270 (MONDO ID normalized) - Use for full MONDO URI: ?disease wdtn:P5270 ?mondoIRI (returns URI)
- For drug queries, use wdt:P2175 from drug to disease
- For MONDO mappings: Use wdt:P5270 or wdtn:P5270, NOT skos:exactMatch

MULTI-HOP DRUG QUERIES:
- Drug queries need 3 steps: Entity Resolution → Wikidata (get diseases + MONDO) → NDE (get datasets)
- Step 1: entity_resolution to resolve drug name to Wikidata IRI
- Step 2: Query Wikidata for diseases treated by drug (use {{step1.drug_iris}}) AND their MONDO IDs (wdt:P5270/wdtn:P5270)
- Step 3: Query NDE for datasets using MONDO IRIs from step2
- Use OPTIONAL for MONDO properties to still get diseases without MONDO mappings
- If no MONDO mappings, system will fallback to text search using disease labels

CRITICAL - Available result fields for template replacement:
- {{stepN.disease_iris}} - array of disease/MONDO IRIs (from entity_resolution or query results)
- {{stepN.gene_iris}} - array of gene IRIs (from entity_resolution or query results)
- {{stepN.drug_iris}} - array of drug IRIs (from entity_resolution step)
- {{stepN.species_iris}} - array of species IRIs (from entity_resolution or query results)
- {{stepN.entity_iris}} - generic array of entity IRIs (from entity_resolution step)
- {{stepN.dataset_ids}} - array of dataset IDs

ALWAYS use "disease_iris" (plural with underscore), NEVER "mondoIRI" or "diseases"
- Entity resolution steps output: drug_iris, gene_iris, disease_iris, or entity_iris based on entity_type

IMPORTANT: You MUST return ONLY valid JSON. Do not include any explanatory text, comments, or markdown before or after the JSON object. Start your response with { and end with }.
`;
}
