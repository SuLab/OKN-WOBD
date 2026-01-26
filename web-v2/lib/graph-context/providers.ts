/**
 * Graph Context Providers
 * 
 * Implementations of GraphContextProvider for different sources.
 */

import fs from "fs/promises";
import path from "path";
import { GraphContext, GraphContextProvider, ContextFileFormat } from "./types";
import { adaptContextFileToGraphContext } from "./context-adapter";

/**
 * GitHub provider for graph context files (*_global.json)
 */
export class GitHubContextProvider implements GraphContextProvider {
    private baseUrl: string;
    private cache: Map<string, { context: GraphContext; timestamp: number }> = new Map();
    private cacheTTL: number = 24 * 60 * 60 * 1000; // 24 hours

    constructor(baseUrl?: string) {
        this.baseUrl = baseUrl ?? process.env.GITHUB_CONTEXT_URL ?? "";
    }

    getSource(): "github" {
        return "github";
    }

    supports(graphShortname: string): boolean {
        // We support any graph that has a context file on GitHub
        // In practice, we'll try to load it and return null if it doesn't exist
        return true;
    }

    async loadContext(graphShortname: string): Promise<GraphContext | null> {
        if (!this.baseUrl) return null;

        // Check cache first
        const cached = this.cache.get(graphShortname);
        if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
            return cached.context;
        }

        try {
            const url = `${this.baseUrl}/${graphShortname}_global.json`;
            const response = await fetch(url);

            if (!response.ok) {
                if (response.status === 404) {
                    return null; // Graph not found
                }
                throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
            }

            const contextFile: ContextFileFormat = await response.json();
            const context = adaptContextFileToGraphContext(graphShortname, contextFile, "github");

            // Cache the result
            this.cache.set(graphShortname, {
                context,
                timestamp: Date.now(),
            });

            return context;
        } catch (error) {
            console.error(`Error loading GitHub context for ${graphShortname}:`, error);
            return null;
        }
    }

    /**
     * Clear cache for a specific graph or all graphs
     */
    clearCache(graphShortname?: string): void {
        if (graphShortname) {
            this.cache.delete(graphShortname);
        } else {
            this.cache.clear();
        }
    }
}

/**
 * Local file provider for *_global.json context files
 */
export class LocalFileProvider implements GraphContextProvider {
    private contextDir: string;

    constructor(contextDir?: string) {
        // Use environment variable or default to web-v2/context/graphs
        this.contextDir = contextDir ||
            (process.env.GRAPH_CONTEXT_DIR ? path.resolve(process.env.GRAPH_CONTEXT_DIR) :
                path.join(process.cwd(), "context", "graphs"));
    }

    getSource(): "local" {
        return "local";
    }

    supports(graphShortname: string): boolean {
        // Check if file exists (async check in loadContext)
        return true;
    }

    async loadContext(graphShortname: string): Promise<GraphContext | null> {
        try {
            const filePath = path.join(this.contextDir, `${graphShortname}_global.json`);

            // Check if file exists
            try {
                await fs.access(filePath);
            } catch {
                return null; // File doesn't exist
            }

            const fileContent = await fs.readFile(filePath, "utf-8");
            const contextFile: ContextFileFormat = JSON.parse(fileContent);
            const context = adaptContextFileToGraphContext(graphShortname, contextFile, "local");

            return context;
        } catch (error) {
            console.error(`Error loading local context for ${graphShortname}:`, error);
            return null;
        }
    }

    /**
     * Save context to local file (useful for caching from GitHub)
     */
    async saveContext(context: GraphContext): Promise<void> {
        try {
            // Ensure directory exists
            await fs.mkdir(this.contextDir, { recursive: true });

            const filePath = path.join(this.contextDir, `${context.graph_shortname}_global.json`);

            // Convert back to context file format for storage
            const contextFile: ContextFileFormat = {
                endpoint: context.endpoint,
                prefixes: context.prefixes,
                classes: context.classes.map((cls) => ({
                    iri: cls.iri,
                    count: cls.count,
                })),
                dataset_properties: context.properties,
            };

            await fs.writeFile(filePath, JSON.stringify(contextFile, null, 2), "utf-8");
        } catch (error) {
            console.error(`Error saving local context for ${context.graph_shortname}:`, error);
            throw error;
        }
    }
}

