/**
 * Graph Context Loader
 * 
 * Main loader that orchestrates multiple providers to load graph context.
 * Tries providers in order until one succeeds.
 */

import { GraphContext, GraphContextProvider } from "./types";

// Lazy imports for providers to avoid bundling fs/promises in client
// These are only loaded when actually needed (server-side)
async function getProviders() {
    if (typeof window !== "undefined") {
        return null; // Not available on client
    }
    return await import("./providers");
}

async function getLocalFileProvider() {
    const providers = await getProviders();
    if (!providers) return null;
    return new providers.LocalFileProvider();
}

async function getGitHubContextProvider() {
    const providers = await getProviders();
    if (!providers) return null;
    return new providers.GitHubContextProvider();
}

export class GraphContextLoader {
    private providers: GraphContextProvider[] = [];
    private localFileProvider: GraphContextProvider | null = null;

    constructor(providers?: GraphContextProvider[]) {
        if (providers) {
            this.providers = providers;
        } else {
            // Providers will be added lazily when needed (server-side only)
            this.providers = [];
        }
    }

    // Lazy initialization of providers (server-only)
    private async ensureProviders(): Promise<void> {
        if (typeof window !== "undefined") return; // Skip on client
        if (this.providers.length > 0) return; // Already initialized
        
        // Add LocalFileProvider first (highest priority)
        const localProvider = await getLocalFileProvider();
        if (localProvider) {
            this.localFileProvider = localProvider;
            this.providers.push(localProvider);
        }
        
        // Add GitHubContextProvider if not disabled
        const disabled = process.env.DISABLE_GITHUB_CONTEXT === "1" || 
                       process.env.DISABLE_GITHUB_CONTEXT === "true";
        if (!disabled) {
            const githubProvider = await getGitHubContextProvider();
            if (githubProvider) {
                this.providers.push(githubProvider);
            }
        }
    }

    /**
     * Load context for a specific graph
     * Tries providers in order until one succeeds
     */
    async loadContext(graphShortname: string): Promise<GraphContext | null> {
        // Ensure providers are initialized (server-only, lazy init)
        await this.ensureProviders();

        for (const provider of this.providers) {
            if (!provider.supports(graphShortname)) {
                continue;
            }

            const context = await provider.loadContext(graphShortname);
            if (context) {
                // If we got it from GitHub and we have a local provider, cache it
                if (context.source === "github" && this.localFileProvider) {
                    const providers = await getProviders();
                    if (providers && provider instanceof providers.GitHubContextProvider) {
                        // Cache asynchronously (don't wait)
                        (this.localFileProvider as any).saveContext(context).catch((err: unknown) => {
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
    async clearCache(graphShortname?: string): Promise<void> {
        await this.ensureProviders();
        const providers = await getProviders();
        if (!providers) return;
        
        for (const provider of this.providers) {
            if (provider instanceof providers.GitHubContextProvider) {
                provider.clearCache(graphShortname);
            }
        }
        // Note: LocalFileProvider doesn't have a clearCache method
    }
}

// Export a singleton instance
export const graphContextLoader = new GraphContextLoader();

