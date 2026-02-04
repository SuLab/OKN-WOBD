/**
 * Graph Context Providers
 * 
 * Implementations of GraphContextProvider for different sources.
 * 
 * NOTE: This file uses Node.js fs/promises and should only be used on the server.
 * Importing this in client components will cause build errors.
 * 
 * This file should only be imported in:
 * - API routes (app/api/**)
 * - Server components
 * - Server actions
 * 
 * DO NOT import this in client components (files with "use client").
 */

// Server-only check - throw immediately if imported on client
// This prevents webpack from trying to bundle fs/promises for the client
if (typeof window !== "undefined" || typeof document !== "undefined") {
    const error = new Error(
        "graph-context/providers cannot be imported in client components. " +
        "This module uses Node.js fs/promises and is server-only. " +
        "Import this only in API routes or server components."
    );
    // Prevent the module from loading
    throw error;
}

import path from "path";
import { GraphContext, GraphContextProvider, ContextFileFormat } from "./types";
import { adaptContextFileToGraphContext } from "./context-adapter";

// Dynamic import for fs/promises (server-side only)
// This function is only called on the server after the early throw check
async function getFs() {
    // Use a template string to make the import path dynamic
    // Combined with webpack config, this should prevent client bundling
    // @ts-ignore - fs/promises is a Node.js built-in, only available server-side
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    return await import(`fs${"/"}promises`);
}

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
            const fs = await getFs();
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
            const fs = await getFs();
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

