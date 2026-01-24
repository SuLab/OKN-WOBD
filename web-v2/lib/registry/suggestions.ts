// Generate query/topic suggestions based on graph content and context packs

import type { RegistryGraphInfo } from "./graphs";
import { executeSPARQL } from "@/lib/sparql/executor";
import { loadContextPack } from "@/lib/context-packs/loader";
import { proxyLLMCall } from "@/lib/llm/proxy";
import { graphContextLoader } from "@/lib/graph-context/loader";
import type { GraphContext } from "@/lib/graph-context/types";

// Get shared API key from environment
function getSharedAPIKey(): string | null {
    return process.env.OPENAI_SHARED_API_KEY || null;
}

const FRINK_FEDERATION_URL = process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
    "https://frink.apps.renci.org/federation/sparql";

export interface QuerySuggestion {
    question: string; // Scientific question
    description: string;
    exampleQuery: string;
    graphShortnames: string[];
    basedOn?: string; // What this suggestion is based on (e.g., "health conditions found", "context pack template")
}

interface GraphContent {
    healthConditions: string[];
    species: string[];
    datasetTypes: string[];
    sampleDatasets: Array<{ name: string; description?: string }>;
    commonProperties: Array<{ uri: string; count: number }>;
}

/**
 * Query actual content from a graph to discover real values
 * First tries to load from omnigraph context, then falls back to live queries
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

    // Try to load from omnigraph context first
    try {
        const context = await graphContextLoader.loadContext(graphShortname);
        if (context) {
            // Use data from omnigraph context
            content.healthConditions = context.healthConditions || [];
            content.species = context.species || [];
            content.sampleDatasets = context.sampleDatasets || [];

            // Convert classes to datasetTypes
            content.datasetTypes = context.classes
                .map(cls => {
                    // Extract readable name from IRI
                    const parts = cls.iri.split("/");
                    return parts[parts.length - 1];
                })
                .filter(Boolean);

            // Convert properties to commonProperties
            content.commonProperties = Object.values(context.properties)
                .map(prop => ({
                    uri: prop.iri,
                    count: prop.count,
                }))
                .sort((a, b) => b.count - a.count)
                .slice(0, 20);

            // If we got good data from omnigraph, return early (but can enhance with queries)
            if (content.healthConditions.length > 0 || content.species.length > 0 || content.sampleDatasets.length > 0) {
                // Still query live for more up-to-date counts, but we have base data
                // For now, return what we have from omnigraph
                return content;
            }
        }
    } catch (error) {
        console.warn(`Failed to load omnigraph context for ${graphShortname}:`, error);
        // Continue to live queries below
    }

    // Fall back to live queries if omnigraph context is unavailable or incomplete
    try {
        // Query 1: Find real health conditions
        const healthConditionsQuery = `
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?condition (COUNT(?dataset) AS ?count)
FROM <${graphIri}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:healthCondition ?condition .
}
GROUP BY ?condition
ORDER BY DESC(?count)
LIMIT 15
`;

        const healthResult = await executeSPARQL(healthConditionsQuery, FRINK_FEDERATION_URL);
        if (healthResult.result?.results?.bindings) {
            content.healthConditions = healthResult.result.results.bindings
                .map((b: any) => {
                    const value = b.condition?.value || "";
                    // Extract readable name from URI or use as-is if it's a string
                    if (value.startsWith("http")) {
                        const parts = value.split("/");
                        return parts[parts.length - 1].replace(/_/g, " ");
                    }
                    return value;
                })
                .filter(Boolean);
        }

        // Query 2: Find real species
        const speciesQuery = `
PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?species (COUNT(?dataset) AS ?count)
FROM <${graphIri}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:species ?species .
}
GROUP BY ?species
ORDER BY DESC(?count)
LIMIT 10
`;

        const speciesResult = await executeSPARQL(speciesQuery, FRINK_FEDERATION_URL);
        if (speciesResult.result?.results?.bindings) {
            content.species = speciesResult.result.results.bindings
                .map((b: any) => {
                    const value = b.species?.value || "";
                    if (value.startsWith("http")) {
                        const parts = value.split("/");
                        return parts[parts.length - 1].replace(/_/g, " ");
                    }
                    return value;
                })
                .filter(Boolean);
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

    // Build context for LLM, including graph context if available
    const context = {
        graph: { shortname: graphShortname, label: graphLabel },
        discoveredContent: {
            healthConditions: content.healthConditions.slice(0, 10),
            species: content.species.slice(0, 10),
            sampleDatasets: content.sampleDatasets.slice(0, 5),
        },
        contextPack: {
            templates: contextPack?.templates || [],
            schemaHints: contextPack?.schema_hints || {},
        },
        graphContext: graphContext ? {
            classes: graphContext.classes.slice(0, 10).map(c => `${c.iri} (${c.count})`),
            prefixes: Object.keys(graphContext.prefixes).slice(0, 10),
        } : undefined,
    };

    // Try to use LLM to generate questions, but fall back to rule-based if no key
    const apiKey = getSharedAPIKey();
    if (apiKey) {
        try {
            const prompt = `You are a scientific data discovery assistant. Based on the following information about a knowledge graph, generate 5-7 specific, actionable scientific questions that researchers could ask of this graph.

Graph: ${graphLabel} (${graphShortname})
Graph IRI: https://purl.org/okn/frink/kg/${graphShortname}

Discovered Content:
- Health Conditions: ${content.healthConditions.length > 0 ? content.healthConditions.join(", ") : "None found"}
- Species: ${content.species.length > 0 ? content.species.join(", ") : "None found"}
- Sample Datasets: ${content.sampleDatasets.slice(0, 3).map(d => d.name).join(", ")}

Context Pack Templates: ${contextPack?.templates?.map((t: any) => t.id).join(", ") || "None"}

Generate scientific questions that:
1. Are specific and actionable (not generic like "find datasets")
2. Reference actual content found in the graph (health conditions, species, etc.)
3. Are phrased as natural language questions researchers would ask
4. Could be answered with SPARQL queries

For each question, also provide a SPARQL query example that could answer it. Use the graph IRI in FROM clauses.

Format your response as JSON array:
[
  {
    "question": "What datasets are available for [specific condition/species]?",
    "description": "Brief description of what this query finds",
    "sparql": "PREFIX schema: <http://schema.org/>\nSELECT ... FROM <https://purl.org/okn/frink/kg/${graphShortname}>\nWHERE { ... }"
  },
  ...
]

Return ONLY the JSON array, no other text.`;

            const llmResponse = await proxyLLMCall(
                {
                    provider: "anthropic",
                    model: "claude-sonnet-4-5",
                    messages: [
                        { role: "system", content: "You are a helpful assistant that generates scientific questions and SPARQL queries for knowledge graphs." },
                        { role: "user", content: prompt },
                    ],
                    temperature: 0.7,
                    max_tokens: 2000,
                },
                apiKey
            );

            if (llmResponse.content) {
                try {
                    // Extract JSON from response (might have markdown code blocks)
                    let jsonStr = llmResponse.content.trim();
                    if (jsonStr.startsWith("```")) {
                        jsonStr = jsonStr.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
                    }
                    const llmSuggestions = JSON.parse(jsonStr);

                    if (Array.isArray(llmSuggestions)) {
                        return llmSuggestions.map((s: any) => ({
                            question: s.question || s.topic || "",
                            description: s.description || "",
                            exampleQuery: s.sparql || s.exampleQuery || "",
                            graphShortnames: [graphShortname],
                            basedOn: "LLM-generated from graph content",
                        })).filter((s: any) => s.question && s.exampleQuery);
                    }
                } catch (parseError) {
                    console.warn("Failed to parse LLM response:", parseError);
                }
            }
        } catch (error) {
            console.warn("LLM generation failed, falling back to rule-based:", error);
        }
    }

    // Fallback: Generate rule-based suggestions from discovered content
    if (content.healthConditions.length > 0) {
        const condition = content.healthConditions[0];
        suggestions.push({
            question: `What datasets are available for ${condition}?`,
            description: `Find datasets related to ${condition} in ${graphLabel}`,
            exampleQuery: `PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?dataset ?name ?description
FROM <https://purl.org/okn/frink/kg/${graphShortname}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:healthCondition ?condition .
  OPTIONAL { ?dataset schema:description ?description . }
  FILTER(CONTAINS(LCASE(STR(?condition)), LCASE("${condition}")))
}
LIMIT 20`,
            graphShortnames: [graphShortname],
            basedOn: `Discovered health condition: ${condition}`,
        });
    }

    if (content.species.length > 0) {
        const species = content.species[0];
        suggestions.push({
            question: `What datasets contain data for ${species}?`,
            description: `Find datasets with ${species} data in ${graphLabel}`,
            exampleQuery: `PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?dataset ?name ?description
FROM <https://purl.org/okn/frink/kg/${graphShortname}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:species ?species .
  OPTIONAL { ?dataset schema:description ?description . }
  FILTER(CONTAINS(LCASE(STR(?species)), LCASE("${species}")))
}
LIMIT 20`,
            graphShortnames: [graphShortname],
            basedOn: `Discovered species: ${species}`,
        });
    }

    if (content.healthConditions.length > 0 && content.species.length > 0) {
        suggestions.push({
            question: `What datasets combine ${content.healthConditions[0]} and ${content.species[0]}?`,
            description: `Find datasets that have both the health condition and species`,
            exampleQuery: `PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?dataset ?name ?description
FROM <https://purl.org/okn/frink/kg/${graphShortname}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:healthCondition ?condition ;
           schema:species ?species .
  OPTIONAL { ?dataset schema:description ?description . }
  FILTER(CONTAINS(LCASE(STR(?condition)), LCASE("${content.healthConditions[0]}")))
  FILTER(CONTAINS(LCASE(STR(?species)), LCASE("${content.species[0]}")))
}
LIMIT 20`,
            graphShortnames: [graphShortname],
            basedOn: `Combined health condition and species`,
        });
    }

    // Add template-based suggestions
    if (contextPack?.templates) {
        for (const template of contextPack.templates) {
            if (template.id === "dataset_search" && content.sampleDatasets.length > 0) {
                suggestions.push({
                    question: `Search for datasets by keywords or topics`,
                    description: template.description || "Find datasets matching specific keywords or health conditions",
                    exampleQuery: `PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?dataset ?name ?description
FROM <https://purl.org/okn/frink/kg/${graphShortname}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description . }
  FILTER(
    REGEX(LCASE(?name), "keyword", "i") ||
    (BOUND(?description) && REGEX(LCASE(?description), "keyword", "i"))
  )
}
LIMIT 20`,
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
            // Load graph context (from omnigraph if available)
            const graphContext = await graphContextLoader.loadContext(shortname);

            // Discover actual content from the graph (uses omnigraph if available, queries if not)
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
            question: `Query across multiple graphs: ${graphShortnames.join(", ")}`,
            description: `Combine data from different knowledge graphs to answer complex questions`,
            exampleQuery: `PREFIX schema: <http://schema.org/>
SELECT ?dataset ?name ?graph
WHERE {
  {
    SELECT ?dataset ?name
    FROM <https://purl.org/okn/frink/kg/${graphShortnames[0]}>
    WHERE {
      ?dataset a schema:Dataset ;
               schema:name ?name .
    }
    LIMIT 10
  }
  BIND("${graphShortnames[0]}" AS ?graph)
}
UNION
{
  SELECT ?dataset ?name
  FROM <https://purl.org/okn/frink/kg/${graphShortnames[1]}>
  WHERE {
    ?dataset a schema:Dataset ;
             schema:name ?name .
  }
  LIMIT 10
  BIND("${graphShortnames[1]}" AS ?graph)
}
LIMIT 20`,
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
                        description: template.description || `Find datasets by keywords or health conditions in ${graph.label}`,
                        exampleQuery: `PREFIX schema: <http://schema.org/>
SELECT ?dataset ?name ?description
FROM <https://purl.org/okn/frink/kg/${graph.shortname}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description . }
  FILTER(
    REGEX(LCASE(?name), "your_keywords", "i") ||
    (BOUND(?description) && REGEX(LCASE(?description), "your_keywords", "i"))
  )
}
LIMIT 20`,
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
                description: `Explore datasets related to health conditions, diseases, or medical research`,
                exampleQuery: `PREFIX schema: <http://schema.org/>
SELECT ?dataset ?name ?condition
FROM <https://purl.org/okn/frink/kg/${graph.shortname}>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:healthCondition ?condition . }
}
LIMIT 20`,
                graphShortnames: [graph.shortname],
                basedOn: "Graph description analysis",
            });
        }
    }

    return suggestions;
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
