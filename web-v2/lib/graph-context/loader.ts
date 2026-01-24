/**
 * Graph Context Loader
 * 
 * Main loader that orchestrates multiple providers to load graph context.
 * Tries providers in order until one succeeds.
 */

import { GraphContext, GraphContextProvider } from "./types";
import { OmnigraphGitHubProvider, LocalFileProvider } from "./providers";

export class GraphContextLoader {
    private providers: GraphContextProvider[] = [];

    constructor(providers?: GraphContextProvider[]) {
        if (providers) {
            this.providers = providers;
        } else {
            // Default providers: try local first, then GitHub
            this.providers = [
                new LocalFileProvider(),
                new OmnigraphGitHubProvider(),
            ];
        }
    }

    /**
     * Load context for a specific graph
     * Tries providers in order until one succeeds
     */
    async loadContext(graphShortname: string): Promise<GraphContext | null> {
        for (const provider of this.providers) {
            if (!provider.supports(graphShortname)) {
                continue;
            }

            const context = await provider.loadContext(graphShortname);
            if (context) {
                // If we got it from GitHub and we have a local provider, cache it
                if (context.source === "omnigraph" && provider instanceof OmnigraphGitHubProvider) {
                    const localProvider = this.providers.find((p) => p instanceof LocalFileProvider) as LocalFileProvider;
                    if (localProvider) {
                        // Cache asynchronously (don't wait)
                        localProvider.saveContext(context).catch((err) => {
                            console.warn(`Failed to cache context for ${graphShortname}:`, err);
                        });
                    }
                }
                return context;
            }
        }

        return null; // No provider could load the context
    }

    /**
     * Load context for multiple graphs
     */
    async loadContexts(graphShortnames: string[]): Promise<Map<string, GraphContext>> {
        const contexts = new Map<string, GraphContext>();

        // Load in parallel
        const promises = graphShortnames.map(async (shortname) => {
            const context = await this.loadContext(shortname);
            if (context) {
                contexts.set(shortname, context);
            }
        });

        await Promise.all(promises);

        return contexts;
    }

    /**
     * Add a provider to the loader
     */
    addProvider(provider: GraphContextProvider): void {
        this.providers.push(provider);
    }

    /**
     * Clear cache for a specific graph (if provider supports it)
     */
    clearCache(graphShortname?: string): void {
        for (const provider of this.providers) {
            if (provider instanceof OmnigraphGitHubProvider) {
                provider.clearCache(graphShortname);
            }
        }
    }
}

// Export a singleton instance
export const graphContextLoader = new GraphContextLoader();

