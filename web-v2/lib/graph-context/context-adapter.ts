/**
 * Context Adapter
 *
 * Transforms the *_global.json context file format into our standard GraphContext format.
 */

import { GraphContext, ContextFileFormat } from "./types";

/**
 * Extract health conditions from context file format.
 * Only used when dataset_properties is present (knowledge_graph path).
 */
function extractHealthConditions(datasetProps: Record<string, { iri: string; count: number; curie?: string; examples?: Array<{ subject: string; object: string }> }>): string[] {
    const healthConditionProp = datasetProps["http://schema.org/healthCondition"];
    if (!healthConditionProp?.examples) {
        return [];
    }

    const conditions = new Set<string>();
    for (const example of healthConditionProp.examples) {
        const value = example.object;
        if (value) {
            // Extract readable name from URI or use as-is if it's a string
            if (value.startsWith("http")) {
                const parts = value.split("/");
                const lastPart = parts[parts.length - 1].replace(/_/g, " ");
                conditions.add(lastPart);
            } else {
                conditions.add(value);
            }
        }
    }
    return Array.from(conditions);
}

/**
 * Extract species from context file format.
 * Only used when dataset_properties is present (knowledge_graph path).
 */
function extractSpecies(datasetProps: Record<string, { iri: string; count: number; curie?: string; examples?: Array<{ subject: string; object: string }> }>): string[] {
    const speciesProp = datasetProps["http://schema.org/species"];
    if (!speciesProp?.examples) {
        return [];
    }

    const species = new Set<string>();
    for (const example of speciesProp.examples) {
        const value = example.object;
        if (value) {
            // Extract readable name from URI or use as-is
            if (value.startsWith("http")) {
                // Handle taxonomy URIs like https://www.uniprot.org/taxonomy/11052
                const parts = value.split("/");
                const lastPart = parts[parts.length - 1];
                // Could look up taxonomy name, but for now use ID
                species.add(`taxonomy:${lastPart}`);
            } else {
                species.add(value);
            }
        }
    }
    return Array.from(species);
}

/**
 * Extract sample datasets from context file format.
 * Only used when dataset_properties is present (knowledge_graph path).
 */
function extractSampleDatasets(datasetProps: Record<string, { iri: string; count: number; curie?: string; examples?: Array<{ subject: string; object: string }> }>): Array<{ name: string; description?: string }> {
    const nameProp = datasetProps["http://schema.org/name"];
    const descriptionProp = datasetProps["http://schema.org/description"];

    if (!nameProp?.examples) {
        return [];
    }

    // Build a map of dataset URIs to names
    const datasetNames = new Map<string, string>();
    for (const example of nameProp.examples) {
        if (example.subject && example.object) {
            datasetNames.set(example.subject, example.object);
        }
    }

    // Build a map of dataset URIs to descriptions (if available)
    const datasetDescriptions = new Map<string, string>();
    if (descriptionProp?.examples) {
        for (const example of descriptionProp.examples) {
            if (example.subject && example.object) {
                datasetDescriptions.set(example.subject, example.object);
            }
        }
    }

    // Combine into sample datasets array
    const datasets: Array<{ name: string; description?: string }> = [];
    for (const [subject, name] of datasetNames.entries()) {
        datasets.push({
            name,
            description: datasetDescriptions.get(subject),
        });
    }

    return datasets.slice(0, 20); // Limit to 20 samples
}

/**
 * Transform context file format to GraphContext
 */
export function adaptContextFileToGraphContext(
    graphShortname: string,
    contextFile: ContextFileFormat,
    source: "github" | "local" = "github"
): GraphContext {
    const graphIri = `https://purl.org/okn/frink/kg/${graphShortname}`;

    // Use dataset_properties or properties (ontology path); both have compatible shape for context.properties
    const props = contextFile.dataset_properties ?? contextFile.properties ?? {};

    const properties: Record<string, {
        iri: string;
        count: number;
        curie?: string;
        examples?: Array<{ subject: string; object: string }>;
    }> = {};

    for (const [key, prop] of Object.entries(props)) {
        properties[key] = {
            iri: prop.iri,
            count: prop.count,
            curie: prop.curie,
            examples: prop.examples,
        };
    }

    // Derived content only when dataset_properties is present (knowledge_graph path)
    const healthConditions = contextFile.dataset_properties
        ? extractHealthConditions(contextFile.dataset_properties)
        : undefined;
    const species = contextFile.dataset_properties
        ? extractSpecies(contextFile.dataset_properties)
        : undefined;
    const sampleDatasets = contextFile.dataset_properties
        ? extractSampleDatasets(contextFile.dataset_properties)
        : undefined;

    return {
        graph_shortname: graphShortname,
        graph_iri: graphIri,
        endpoint: contextFile.endpoint,
        last_updated: new Date().toISOString(),
        source,
        prefixes: contextFile.prefixes ?? {},
        classes: (contextFile.classes ?? []).map((cls) => ({
            iri: cls.iri,
            count: cls.count,
        })),
        properties,
        healthConditions: healthConditions && healthConditions.length > 0 ? healthConditions : undefined,
        species: species && species.length > 0 ? species : undefined,
        sampleDatasets: sampleDatasets && sampleDatasets.length > 0 ? sampleDatasets : undefined,
    };
}
