/**
 * Omnigraph Adapter
 * 
 * Transforms omnigraph format into our standard GraphContext format.
 */

import { GraphContext, OmnigraphFormat } from "./types";

/**
 * Extract health conditions from omnigraph format
 */
function extractHealthConditions(omnigraph: OmnigraphFormat): string[] {
    const healthConditionProp = omnigraph.dataset_properties["http://schema.org/healthCondition"];
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
 * Extract species from omnigraph format
 */
function extractSpecies(omnigraph: OmnigraphFormat): string[] {
    const speciesProp = omnigraph.dataset_properties["http://schema.org/species"];
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
 * Extract sample datasets from omnigraph format
 */
function extractSampleDatasets(omnigraph: OmnigraphFormat): Array<{ name: string; description?: string }> {
    const nameProp = omnigraph.dataset_properties["http://schema.org/name"];
    const descriptionProp = omnigraph.dataset_properties["http://schema.org/description"];

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
 * Transform omnigraph format to GraphContext
 */
export function adaptOmnigraphToContext(
    graphShortname: string,
    omnigraph: OmnigraphFormat,
    source: "omnigraph" | "local" = "omnigraph"
): GraphContext {
    const graphIri = `https://purl.org/okn/frink/kg/${graphShortname}`;

    // Transform properties from dataset_properties to properties
    const properties: Record<string, {
        iri: string;
        count: number;
        curie?: string;
        examples?: Array<{ subject: string; object: string }>;
    }> = {};

    for (const [key, prop] of Object.entries(omnigraph.dataset_properties)) {
        properties[key] = {
            iri: prop.iri,
            count: prop.count,
            curie: prop.curie,
            examples: prop.examples,
        };
    }

    // Extract derived content
    const healthConditions = extractHealthConditions(omnigraph);
    const species = extractSpecies(omnigraph);
    const sampleDatasets = extractSampleDatasets(omnigraph);

    return {
        graph_shortname: graphShortname,
        graph_iri: graphIri,
        endpoint: omnigraph.endpoint,
        last_updated: new Date().toISOString(),
        source,
        prefixes: omnigraph.prefixes,
        classes: omnigraph.classes.map((cls) => ({
            iri: cls.iri,
            count: cls.count,
        })),
        properties,
        healthConditions: healthConditions.length > 0 ? healthConditions : undefined,
        species: species.length > 0 ? species : undefined,
        sampleDatasets: sampleDatasets.length > 0 ? sampleDatasets : undefined,
    };
}

