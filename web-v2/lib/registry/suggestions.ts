// Generate query/topic suggestions based on graph content and context packs

import type { RegistryGraphInfo } from "./graphs";
import { executeSPARQL } from "@/lib/sparql/executor";
import { loadContextPack } from "@/lib/context-packs/loader";
import { proxyLLMCall } from "@/lib/llm/proxy";
import { graphContextLoader } from "@/lib/graph-context/loader";
import type { GraphContext } from "@/lib/graph-context/types";

// Get shared API key for Anthropic (suggestions use provider: "anthropic")
function getSharedAPIKey(): string | null {
    return process.env.ANTHROPIC_SHARED_API_KEY
        || process.env.ANTHROPIC_API_KEY
        || null;
}

const FRINK_FEDERATION_URL = process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
    "https://frink.apps.renci.org/federation/sparql";

/** Common NCBITaxon IDs to human-readable species names when rdfs:label is not in graph */
const COMMON_SPECIES: Record<string, string> = {
    "9606": "human",
    "10090": "mouse",
    "10116": "rat",
    "3702": "thale cress",
    "7227": "fruit fly",
    "4932": "yeast",
};

/** True if the value looks like a CURIE, IRI, or ontology ID (not a human-readable label). */
function isLikelyCurieOrIri(value: string): boolean {
    if (!value || typeof value !== "string") return true;
    const s = value.trim();
    if (s.startsWith("http://") || s.startsWith("https://")) return true;
    if (/^\w+:\S+$/.test(s)) return true; // e.g. MONDO:0005015, NCIT:C115935
    if (/^\d+$/.test(s)) return true;     // e.g. 9606
    if (/\w+\s+C?\d+/.test(s)) return true; // e.g. NCIT C115935
    return false;
}

/** Prefer a human-readable label; return null if we only have a CURIE/IRI we can't use. */
function preferLabel(iri: string, label: string | undefined): string | null {
    if (label && label.trim() && !isLikelyCurieOrIri(label)) return label.trim();
    if (isLikelyCurieOrIri(iri)) return null;
    return iri.trim() || null;
}

/** Like preferLabel, but also resolves common species IDs (e.g. 9606 → human) when no label. */
function resolveSpeciesLabel(iri: string, label: string | undefined): string | null {
    const p = preferLabel(iri, label);
    if (p) return p;
    const m = iri.match(/(?:NCBITaxon_)?(\d+)$/) || (/^(\d+)$/.test(iri) ? [iri, iri] : null);
    if (m && COMMON_SPECIES[m[1]]) return COMMON_SPECIES[m[1]];
    return null;
}

export interface QuerySuggestion {
    question: string; // Natural-language question researchers can ask
    description: string;
    exampleQuery?: string; // Optional; @suggest is natural-language-only, so typically omitted
    graphShortnames: string[];
    basedOn?: string; // What this suggestion is based on (e.g., "health conditions found", "context pack template")
}

interface GraphContent {
    healthConditions: string[];
    species: string[];
    hasHealthConditions?: boolean; // true when graph has condition dimension but we have no human-readable labels
    hasSpecies?: boolean;          // true when graph has species dimension but we have no human-readable labels
    datasetTypes: string[];
    sampleDatasets: Array<{ name: string; description?: string }>;
    commonProperties: Array<{ uri: string; count: number }>;
}

/**
 * Query actual content from a graph to discover real values
 * First tries to load from graph context (*_global.json), then falls back to live queries
 */
async function discoverGraphContent(graphShortname: string): Promise<GraphContent> {
    const graphIri = `https://purl.org/okn/frink/kg/${graphShortname}`;

    const content: GraphContent = {
        healthConditions: [],
        species: [],
        datasetTypes: [],
        sampleDatasets: [],
        commonProperties: [],
    };

    // Try to load from graph context first
    try {
        const context = await graphContextLoader.loadContext(graphShortname);
        if (context) {
            const rawConditions = context.healthConditions || [];
            const rawSpecies = context.species || [];
            content.hasHealthConditions = rawConditions.length > 0;
            content.hasSpecies = rawSpecies.length > 0;
            content.healthConditions = rawConditions.filter((v) => !isLikelyCurieOrIri(v));
            content.species = rawSpecies.map((v) => resolveSpeciesLabel(v, v)).filter((v): v is string => v != null);
            content.sampleDatasets = context.sampleDatasets || [];

            content.datasetTypes = context.classes
                .map(cls => cls.iri.split("/").pop() || "")
                .filter(Boolean);
            content.commonProperties = Object.values(context.properties)
                .map(prop => ({ uri: prop.iri, count: prop.count }))
                .sort((a, b) => b.count - a.count)
                .slice(0, 20);

            if (content.healthConditions.length > 0 || content.species.length > 0 || content.sampleDatasets.length > 0 || content.hasHealthConditions || content.hasSpecies) {
                return content;
            }
        }
    } catch (error) {
        console.warn(`Failed to load graph context for ${graphShortname}:`, error);
    }

    // Fall back to live queries if graph context is unavailable or incomplete
    try {
        // Query 1: Find real health conditions; nde uses schema:name on disease entities, also try rdfs:label/skos:prefLabel
        const healthConditionsQuery = `
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?condition (COUNT(?dataset) AS ?count) ?conditionLabel
FROM <${graphIri}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:healthCondition ?condition .
  OPTIONAL { ?condition schema:name ?schemaName . }
  OPTIONAL { ?condition rdfs:label ?rdfsLabel . }
  OPTIONAL { ?condition skos:prefLabel ?skosLabel . }
  BIND(COALESCE(?schemaName, ?rdfsLabel, ?skosLabel, "") AS ?conditionLabel)
}
GROUP BY ?condition ?conditionLabel
ORDER BY DESC(?count)
LIMIT 15
`;

        const healthResult = await executeSPARQL(healthConditionsQuery, FRINK_FEDERATION_URL);
        if (healthResult.result?.results?.bindings) {
            const bindings = healthResult.result.results.bindings;
            content.hasHealthConditions = bindings.length > 0;
            const seen = new Set<string>();
            content.healthConditions = bindings
                .map((b: any) => preferLabel(b.condition?.value || "", b.conditionLabel?.value))
                .filter((v): v is string => v != null && (seen.has(v) ? false : (seen.add(v), true)));
        }

        // Query 2: Find real species; nde uses schema:name on species entities, also try rdfs:label/skos:prefLabel and COMMON_SPECIES
        const speciesQuery = `
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?species (COUNT(?dataset) AS ?count) ?speciesLabel
FROM <${graphIri}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:species ?species .
  OPTIONAL { ?species schema:name ?schemaName . }
  OPTIONAL { ?species rdfs:label ?rdfsLabel . }
  OPTIONAL { ?species skos:prefLabel ?skosLabel . }
  BIND(COALESCE(?schemaName, ?rdfsLabel, ?skosLabel, "") AS ?speciesLabel)
}
GROUP BY ?species ?speciesLabel
ORDER BY DESC(?count)
LIMIT 10
`;

        const speciesResult = await executeSPARQL(speciesQuery, FRINK_FEDERATION_URL);
        if (speciesResult.result?.results?.bindings) {
            const bindings = speciesResult.result.results.bindings;
            content.hasSpecies = bindings.length > 0;
            const seenS = new Set<string>();
            content.species = bindings
                .map((b: any) => resolveSpeciesLabel(b.species?.value || "", b.speciesLabel?.value))
                .filter((v): v is string => v != null && (seenS.has(v) ? false : (seenS.add(v), true)));
        }

        // Query 3: Get sample datasets with names and descriptions
        const datasetsQuery = `
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?name ?description
FROM <${graphIri}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description . }
}
LIMIT 20
`;

        const datasetsResult = await executeSPARQL(datasetsQuery, FRINK_FEDERATION_URL);
        if (datasetsResult.result?.results?.bindings) {
            content.sampleDatasets = datasetsResult.result.results.bindings.map((b: any) => ({
                name: b.name?.value || "",
                description: b.description?.value || "",
            })).filter((d: any) => d.name);
        }

        // Query 4: Find common properties used with datasets
        const propertiesQuery = `
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?property (COUNT(?dataset) AS ?count)
FROM <${graphIri}>
WHERE {
  ?dataset a schema:Dataset .
  ?dataset ?property ?value .
  FILTER(?property != rdf:type)
}
GROUP BY ?property
ORDER BY DESC(?count)
LIMIT 20
`;

        const propertiesResult = await executeSPARQL(propertiesQuery, FRINK_FEDERATION_URL);
        if (propertiesResult.result?.results?.bindings) {
            content.commonProperties = propertiesResult.result.results.bindings.map((b: any) => ({
                uri: b.property?.value || "",
                count: parseInt(b.count?.value || "0", 10),
            }));
        }
    } catch (error) {
        console.warn(`Failed to discover content for graph ${graphShortname}:`, error);
    }

    return content;
}

/**
 * Generate scientific questions using LLM based on discovered graph content
 */
async function generateScientificQuestions(
    graphShortname: string,
    graphLabel: string,
    content: GraphContent,
    contextPack: any,
    graphContext?: GraphContext
): Promise<QuerySuggestion[]> {
    const suggestions: QuerySuggestion[] = [];

    // Try to use LLM to generate questions, but fall back to rule-based if no key
    const apiKey = getSharedAPIKey();
    if (apiKey) {
        try {
            const graphMeta = contextPack?.graphs_metadata?.find((g: any) => g.id === graphShortname);
            const queryableBy = (graphMeta?.queryable_by as any[] || [])
                .map((q: any) => `${q.entity_type} (${q.property || "?"})`)
                .join(", ") || "datasets by keywords";
            const examplePredicates = (graphMeta?.example_predicates as string[] || []).slice(0, 5).join(", ") || "—";

            const healthLine = content.healthConditions.length > 0
                ? `Health conditions (use these names): ${content.healthConditions.slice(0, 8).join(", ")}`
                : content.hasHealthConditions
                    ? "Health conditions: graph has disease/condition dimension (use general terms like 'disease', 'health condition', 'a specific disease')"
                    : "Health conditions: none found";
            const speciesLine = content.species.length > 0
                ? `Species (use these names): ${content.species.slice(0, 8).join(", ")}`
                : content.hasSpecies
                    ? "Species: graph has species dimension (use general terms like 'species', 'a specific species', 'human', 'mouse')"
                    : "Species: none found";

            const prompt = `You are a helpful chat assistant that knows this knowledge graph. A user is asking what they can ask you. Generate 5-7 things they could type into the chat—conversational, like suggesting to a colleague. Mix: short ("Which datasets have human data?"), a bit longer ("I'm looking for datasets that combine a disease and a species—what's available?"), and exploratory ("Find datasets by keyword, e.g. COVID or gene expression"). Provide only natural-language questions and a one-line description—no SPARQL.

Graph: ${graphLabel} (${graphShortname})

What's in this graph:
- ${healthLine}
- ${speciesLine}
- Sample Datasets: ${content.sampleDatasets.slice(0, 3).map(d => d.name).join(", ") || "none"}

Queryable by (use these): ${queryableBy}
Example predicates: ${examplePredicates}

Templates available: ${contextPack?.templates?.map((t: any) => t.id).join(", ") || "None"}

Rules:
1. Do NOT use CURIEs, IRIs, or ontology IDs (no NCIT C115935, 9606, MONDO:0005015). Use plain terms: "disease", "cancer", "human", "mouse", or "a specific disease", "a health condition", "a species".
2. If we have specific labels above, you may use those; otherwise use only general terms.
3. Phrase like something a researcher would actually type in a chat—not a menu or FAQ. Varied, natural.
4. Only suggest concrete questions that can be answered by querying for datasets (by disease, species, pathogen, or keywords). Do NOT suggest meta-questions like "What can I search for?" or "What's in this graph?"—those do not map to a single query and return nothing.

Format as a JSON array with only "question" and "description":
[
  { "question": "...", "description": "..." },
  ...
]

Return ONLY the JSON array.`;

            const llmResponse = await proxyLLMCall(
                {
                    provider: "anthropic",
                    model: "claude-sonnet-4-5",
                    messages: [
                        { role: "system", content: "You help users discover what they can ask about a knowledge graph. Phrase suggestions like a colleague would—conversational, varied, the kinds of things people type in chat." },
                        { role: "user", content: prompt },
                    ],
                    temperature: 0.7,
                    max_tokens: 2000,
                },
                apiKey
            );

            if (llmResponse.text) {
                try {
                    // Extract JSON from response (might have markdown code blocks)
                    let jsonStr = llmResponse.text.trim();
                    if (jsonStr.startsWith("```")) {
                        jsonStr = jsonStr.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
                    }
                    const llmSuggestions = JSON.parse(jsonStr);

                    if (Array.isArray(llmSuggestions)) {
                        return llmSuggestions
                            .map((s: any) => ({
                                question: s.question || s.topic || "",
                                description: s.description || "",
                                graphShortnames: [graphShortname],
                                basedOn: "LLM-generated from graph content",
                            }))
                            .filter((s: any) => s.question);
                    }
                } catch (parseError) {
                    console.warn("Failed to parse LLM response:", parseError);
                }
            }
        } catch (error) {
            console.warn("LLM generation failed, falling back to rule-based:", error);
        }
    }

    // Fallback: Generate rule-based suggestions from discovered content (natural-language only).
    // Use human-readable labels when available; otherwise generic phrasing so we never show CURIEs/IRIs.
    if (content.healthConditions.length > 0) {
        suggestions.push({
            question: `What datasets are available for ${content.healthConditions[0]}?`,
            description: `Finds datasets related to ${content.healthConditions[0]}.`,
            graphShortnames: [graphShortname],
            basedOn: `Discovered health condition: ${content.healthConditions[0]}`,
        });
    } else if (content.hasHealthConditions) {
        suggestions.push({
            question: `What datasets are available for a specific disease or health condition?`,
            description: `Finds datasets by disease or health condition.`,
            graphShortnames: [graphShortname],
            basedOn: "Graph includes health condition dimension",
        });
    }

    if (content.species.length > 0) {
        suggestions.push({
            question: `What datasets contain data for ${content.species[0]}?`,
            description: `Finds datasets with ${content.species[0]} data.`,
            graphShortnames: [graphShortname],
            basedOn: `Discovered species: ${content.species[0]}`,
        });
    } else if (content.hasSpecies) {
        suggestions.push({
            question: `What datasets contain data for a specific species?`,
            description: `Finds datasets by species.`,
            graphShortnames: [graphShortname],
            basedOn: "Graph includes species dimension",
        });
    }

    if (content.healthConditions.length > 0 && content.species.length > 0) {
        suggestions.push({
            question: `What datasets combine ${content.healthConditions[0]} and ${content.species[0]}?`,
            description: `Finds datasets that have both.`,
            graphShortnames: [graphShortname],
            basedOn: "Combined health condition and species",
        });
    } else if (content.hasHealthConditions && content.hasSpecies) {
        suggestions.push({
            question: `What datasets combine a disease or health condition with a species?`,
            description: `Finds datasets that have both dimensions.`,
            graphShortnames: [graphShortname],
            basedOn: "Graph includes health condition and species dimensions",
        });
    }

    // Add template-based suggestions
    if (contextPack?.templates) {
        for (const template of contextPack.templates) {
            if (template.id === "dataset_search" && content.sampleDatasets.length > 0) {
                suggestions.push({
                    question: `Search for datasets by keywords or topics`,
                    description: template.description || "Finds datasets by keywords or health conditions.",
                    graphShortnames: [graphShortname],
                    basedOn: `Context pack template: ${template.id}`,
                });
            }
        }
    }

    return suggestions;
}

/**
 * Get query/topic suggestions for one or more graphs based on actual content
 */
export async function getGraphSuggestions(
    graphShortnames: string[],
    packId: string = "wobd"
): Promise<QuerySuggestion[]> {
    const allSuggestions: QuerySuggestion[] = [];
    const contextPack = loadContextPack(packId);

    for (const shortname of graphShortnames) {
        try {
            // Load graph context (from local/GitHub if available)
            const graphContext = await graphContextLoader.loadContext(shortname);

            // Discover actual content from the graph (uses context file if available, live queries if not)
            const content = await discoverGraphContent(shortname);

            // Get graph info for label
            const { fetchGraphsFromRegistry } = await import("./fetch");
            const graphs = await fetchGraphsFromRegistry();
            const graphInfo = graphs.find(g => g.shortname === shortname);
            const graphLabel = graphInfo?.label || shortname;

            // Generate scientific questions based on content and context
            const suggestions = await generateScientificQuestions(
                shortname,
                graphLabel,
                content,
                contextPack,
                graphContext || undefined
            );

            allSuggestions.push(...suggestions);
        } catch (error) {
            console.warn(`Failed to get suggestions for graph ${shortname}:`, error);
        }
    }

    // Generate cross-graph suggestions if multiple graphs
    if (graphShortnames.length > 1) {
        allSuggestions.push({
            question: `What can I find across ${graphShortnames.join(", ")}?`,
            description: "Combines data from these graphs to answer broader questions.",
            graphShortnames,
            basedOn: "Cross-graph query",
        });
    }

    return allSuggestions;
}

/**
 * Get quick topic suggestions without full content exploration
 * Uses graph descriptions and context pack templates
 */
export function getQuickSuggestions(
    graphs: RegistryGraphInfo[],
    packId: string = "wobd"
): QuerySuggestion[] {
    const suggestions: QuerySuggestion[] = [];
    const contextPack = loadContextPack(packId);

    for (const graph of graphs) {
        const desc = graph.description?.toLowerCase() || "";

        // Use context pack templates if available
        if (contextPack?.templates) {
            for (const template of contextPack.templates) {
                if (template.id === "dataset_search") {
                    suggestions.push({
                        question: `Search for datasets in ${graph.label}`,
                        description: template.description || "Finds datasets by keywords or health conditions.",
                        graphShortnames: [graph.shortname],
                        basedOn: `Context pack template: ${template.id}`,
                    });
                }
            }
        }

        // Add domain-specific suggestions based on description
        if (desc.includes("health") || desc.includes("disease") || desc.includes("medical")) {
            suggestions.push({
                question: `What health-related datasets are available in ${graph.label}?`,
                description: "Finds datasets related to health, diseases, or medical research.",
                graphShortnames: [graph.shortname],
                basedOn: "Graph description analysis",
            });
        }
    }

    return suggestions;
}

/** Category of imperative query suggestions for @suggest (hardcoded, one-line, no subtext) */
export interface SuggestionCategory {
    name: string;
    queries: string[];
}

/**
 * Hardcoded imperative suggestions for @suggest.
 * - Imperative: Find..., Show me..., Which...
 * - No explanatory subtext
 * - Well-known entities (SARS-CoV-2, diabetes, mouse, zebrafish)
 * - Grouped by category; 15–20 total; compatible with NDE dataset_search.
 */
export function getHardcodedSuggestions(): SuggestionCategory[] {
    return [
        {
            name: "Dataset Discovery",
            queries: [
                "Find RNA-seq datasets about SARS-CoV-2",
                "Show me mouse diabetes datasets",
                "Which datasets study immune response in lung tissue?",
                "Find COVID-19 datasets",
                "Show me influenza datasets with human data",
                "Find vaccine-related datasets",
                "Which datasets study Long COVID?",
            ],
        },
        {
            name: "Genes & Diseases",
            queries: [
                "Which datasets study genes involved in cancer?",
                "Find datasets about gene expression in Alzheimer's disease",
                "Which datasets study immune-related genes?",
            ],
        },
        {
            name: "Drugs & Treatments",
            queries: [
                "Find datasets about artemisinin and malaria",
                "Which datasets study metformin?",
                "Find tuberculosis treatment datasets",
            ],
        },
        {
            name: "By Organism",
            queries: [
                "Show me zebrafish developmental biology datasets",
                "Find C. elegans aging studies",
                "Show me human cancer datasets",
                "Find mouse immunology datasets",
                "Which datasets use rat models for diabetes?",
                "Show me primate infectious disease datasets",
            ],
        },
    ];
}

/**
 * Future enhancement: Query NIH Reporter or PubMed for recent/highly cited papers
 * This would help identify "hot topics" in the research community
 * 
 * TODO: Implement when API access is available
 */
export async function getHotTopicsFromLiterature(
    graphShortname: string,
    content: GraphContent
): Promise<string[]> {
    // Placeholder for future implementation
    // Would query:
    // - NIH Reporter API for recent grants related to discovered health conditions/species
    // - PubMed API for recent/highly cited papers
    // - Return list of hot topics that could inform suggestions

    return [];
}
