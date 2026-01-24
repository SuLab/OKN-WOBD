/**
 * Graph Context Type Definitions
 * 
 * Defines the structure for graph context data that can be loaded from
 * multiple sources (local files, omnigraph GitHub, future API endpoints).
 */

/**
 * Standard graph context format used by our application
 */
export interface GraphContext {
    graph_shortname: string;
    graph_iri: string;
    endpoint?: string;
    last_updated: string;
    source: "local" | "omnigraph" | "api";

    prefixes: Record<string, string>;

    classes: Array<{
        iri: string;
        count: number;
        label?: string;
    }>;

    properties: Record<string, {
        iri: string;
        count: number;
        curie?: string;
        examples?: Array<{
            subject: string;
            object: string;
        }>;
    }>;

    // Derived content for suggestions
    healthConditions?: string[];
    species?: string[];
    sampleDatasets?: Array<{
        name: string;
        description?: string;
    }>;
}

/**
 * Omnigraph format (from omnigraph-agent GitHub repo)
 */
export interface OmnigraphFormat {
    endpoint?: string;
    prefixes: Record<string, string>;
    classes: Array<{
        iri: string;
        count: number;
    }>;
    dataset_properties: Record<string, {
        iri: string;
        count: number;
        curie?: string;
        examples?: Array<{
            subject: string;
            object: string;
        }>;
    }>;
}

/**
 * Provider interface for loading graph context from different sources
 */
export interface GraphContextProvider {
    /**
     * Load context for a specific graph
     */
    loadContext(graphShortname: string): Promise<GraphContext | null>;

    /**
     * Check if this provider supports a specific graph
     */
    supports(graphShortname: string): boolean;

    /**
     * Get the source identifier for this provider
     */
    getSource(): "local" | "omnigraph" | "api";
}

