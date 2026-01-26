/**
 * Graph Context Type Definitions
 * 
 * Defines the structure for graph context data that can be loaded from
 * multiple sources (local files, GitHub, future API endpoints).
 */

/**
 * Standard graph context format used by our application
 */
export interface GraphContext {
    graph_shortname: string;
    graph_iri: string;
    endpoint?: string;
    last_updated: string;
    source: "local" | "github" | "api";

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
 * Context file format: the JSON shape of *_global.json files.
 * Extended with optional fields for ontology and OBO views.
 */
export interface ContextFileFormat {
    endpoint?: string;
    /** Human-readable graph description (merged from {graph}.yaml when present). */
    description?: string;
    /** Use-case tags (e.g. dataset_search, entity_lookup). */
    good_for?: string[];
    /** Ontology IDs used or provided (e.g. MONDO, NCBITaxon). */
    uses_ontologies?: string[];
    /** Short descriptions of main relationship patterns. */
    notable_relationships?: string[];
    /** Example predicates with brief notes. */
    example_predicates?: string[];
    /** Entity types and properties useful for querying. */
    queryable_by?: Array<{ entity_type: string; property: string }>;
    prefixes?: Record<string, string>;
    classes?: Array<{
        iri: string;
        count: number;
    }>;
    /** Used for knowledge_graph; adapter uses for properties and healthConditions/species/sampleDatasets when present. */
    dataset_properties?: Record<string, {
        iri: string;
        count: number;
        curie?: string;
        examples?: Array<{
            subject: string;
            object: string;
        }>;
    }>;
    /** Used when there is no dataset_properties (e.g. ontology). Adapter uses for context.properties only. */
    properties?: Record<string, {
        iri: string;
        count: number;
        curie?: string;
        examples?: Array<{
            subject: string;
            object: string;
        }>;
    }>;
    /** For ontology: relations as owl:ObjectProperty, owl:onProperty in Restriction/EquivalentClass, SubObjectPropertyOf. */
    object_properties?: Record<string, {
        iri: string;
        curie?: string;
        label?: string;
        count?: number;
        in_restriction?: Array<{ class_iri: string; filler_iri: string }>;
        examples?: Array<{ subject: string; object: string }>;
    }>;
    /** Predicates for identifier lookups (e.g. schema:identifier, oboInOwl:id). */
    identifier_info?: { predicates: string[] };
    /** Hints for "Find by identifier", "Resolve by label", etc. */
    query_patterns?: Array<{
        pattern: string;
        description: string;
        sparql_hint?: string;
        note?: string;
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
    getSource(): "local" | "github" | "api";
}

