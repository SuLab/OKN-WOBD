// Fetch graph information from OKN Registry
// Registry page: https://frink.renci.org/registry/

import { promises as fs } from "fs";
import path from "path";
import { GRAPHS_DATA, type RegistryGraphInfo } from "./graphs";

const REGISTRY_URL = "https://frink.renci.org/registry/";
const CACHE_TTL = 1000 * 60 * 60 * 24; // 24 hours (1 day)
const GRAPHS_DATA_FILE = path.join(process.cwd(), "data/registry-graphs.json");

// 6pm PT = 1am UTC (next day) or 2am UTC (next day) depending on DST
// We'll check if it's after 6pm PT (01:00 UTC or 02:00 UTC)
function isAfterRefreshTime(): boolean {
    const now = new Date();
    const ptTime = new Date(now.toLocaleString("en-US", { timeZone: "America/Los_Angeles" }));
    const hour = ptTime.getHours();
    return hour >= 18; // 6pm PT = 18:00
}

// Initialize cache with data from file
let cachedGraphs: RegistryGraphInfo[] = [...GRAPHS_DATA];
let cacheTimestamp: number = 0; // Start at 0 to force first fetch

/**
 * Write graphs data back to JSON file
 * Also updates the graphs.ts file for TypeScript imports
 * 
 * Note: File writing may not work in serverless environments (e.g., Vercel)
 * but the in-memory cache will still function correctly.
 */
async function writeGraphsToFile(graphs: RegistryGraphInfo[]): Promise<void> {
    try {
        // Ensure data directory exists
        const dataDir = path.dirname(GRAPHS_DATA_FILE);
        await fs.mkdir(dataDir, { recursive: true });

        // Write JSON file
        const jsonData = {
            lastUpdated: new Date().toISOString(),
            graphs,
        };
        await fs.writeFile(GRAPHS_DATA_FILE, JSON.stringify(jsonData, null, 2), "utf-8");

        // Also update the TypeScript file for imports
        const graphsArray = graphs.map((g) => {
            const desc = g.description ? `    description: ${JSON.stringify(g.description)},\n` : "";
            const endpoint = g.endpoint ? `    endpoint: ${JSON.stringify(g.endpoint)},\n` : "";
            return `  { 
    shortname: ${JSON.stringify(g.shortname)}, 
    label: ${JSON.stringify(g.label)},${desc}${endpoint}  }`;
        }).join(",\n");

        const tsFileContent = `// Registry graph data - auto-updated from OKN Registry
// This file is automatically updated when registry fetch succeeds
// Last updated: ${new Date().toISOString()}
// Source: ${GRAPHS_DATA_FILE}

import type { GraphInfo } from "@/types";

export interface RegistryGraphInfo extends GraphInfo {
  description?: string;
  title?: string;
}

// Initial/fallback graph list - updated automatically from registry
export const GRAPHS_DATA: RegistryGraphInfo[] = [
${graphsArray}
];
`;

        const graphsTsPath = path.join(process.cwd(), "lib/registry/graphs.ts");
        await fs.writeFile(graphsTsPath, tsFileContent, "utf-8");

        console.log(`✅ Updated graphs data files with ${graphs.length} graphs from registry`);
    } catch (error) {
        // File writing may fail in serverless environments (e.g., Vercel)
        // This is expected and non-critical - in-memory cache still works
        console.warn("Note: Could not write graphs to file (expected in serverless environments):", error);
    }
}

/**
 * Fetch graphs from OKN Registry
 * Falls back to cached/file data if registry is unavailable
 */
export async function fetchGraphsFromRegistry(forceRefresh: boolean = false): Promise<RegistryGraphInfo[]> {
    const now = Date.now();
    const cacheAge = now - cacheTimestamp;

    // Check if we should refresh:
    // 1. Force refresh requested
    // 2. Cache is empty (timestamp is 0)
    // 3. Cache is older than 24 hours AND it's after 6pm PT
    const shouldRefresh = forceRefresh || cacheTimestamp === 0 || (cacheAge >= CACHE_TTL && isAfterRefreshTime());

    if (!shouldRefresh && cachedGraphs.length > 0) {
        return cachedGraphs;
    }

    try {
        console.log("Fetching graphs from OKN Registry...");
        // Try to fetch from registry
        const response = await fetch(REGISTRY_URL, {
            headers: {
                "Accept": "text/html,application/json",
            },
            // No Next.js cache for manual refresh
            cache: forceRefresh ? "no-store" : "default",
        });

        if (!response.ok) {
            throw new Error(`Registry fetch failed: ${response.status}`);
        }

        const contentType = response.headers.get("content-type");
        let parsedGraphs: RegistryGraphInfo[];

        // If JSON is available, parse it
        if (contentType?.includes("application/json")) {
            const data = await response.json();
            parsedGraphs = parseRegistryJSON(data);
        } else {
            // Otherwise, parse HTML
            const html = await response.text();
            parsedGraphs = parseRegistryHTML(html);
        }

        // Only update if we got valid graphs
        if (parsedGraphs.length > 0) {
            cachedGraphs = parsedGraphs;
            cacheTimestamp = now;

            // Write to file for persistence
            await writeGraphsToFile(parsedGraphs);

            console.log(`✅ Fetched ${parsedGraphs.length} graphs from registry`);
            return cachedGraphs;
        } else {
            throw new Error("No graphs found in registry response");
        }
    } catch (error) {
        console.warn("Failed to fetch from OKN Registry, using cached/file data:", error);
        // Return cached data (which starts as GRAPHS_DATA from file)
        return cachedGraphs.length > 0 ? cachedGraphs : GRAPHS_DATA;
    }
}

/**
 * Parse registry data from JSON response
 */
function parseRegistryJSON(data: any): RegistryGraphInfo[] {
    // Adapt based on actual JSON structure
    if (Array.isArray(data)) {
        return data.map((item: any) => ({
            shortname: item.shortname || item.id || "",
            label: item.title || item.label || item.name || "",
            description: item.description || "",
            endpoint: item.endpoint || `https://frink.apps.renci.org/${item.shortname}/sparql`,
        }));
    }

    if (data.graphs && Array.isArray(data.graphs)) {
        return data.graphs.map((item: any) => ({
            shortname: item.shortname || item.id || "",
            label: item.title || item.label || item.name || "",
            description: item.description || "",
            endpoint: item.endpoint || `https://frink.apps.renci.org/${item.shortname}/sparql`,
        }));
    }

    return GRAPHS_DATA;
}

/**
 * Parse registry data from HTML page
 * Extracts graph information from the registry page HTML table
 * Table structure: <tr><td><a href="kgs/shortname/">shortname</a></td><td>Title</td><td>Description</td></tr>
 */
function parseRegistryHTML(html: string): RegistryGraphInfo[] {
    const graphs: RegistryGraphInfo[] = [];

    // Extract table rows - each row has: shortname (link), title, description
    // Pattern: <tr>...<td><a href="kgs/shortname/">shortname</a></td><td>Title</td><td>Description</td>...</tr>
    // eslint-disable-next-line no-useless-escape
    const tableRowRegex = /<tr[^>]*>\s*<td[^>]*>\s*<a[^>]*href=["']kgs\/([^\/"']+)\/[^>]*>([^<]+)<\/a>\s*<\/td>\s*<td[^>]*>([^<]+)<\/td>\s*<td[^>]*>([^<]+)<\/td>/gis;

    let match;
    while ((match = tableRowRegex.exec(html)) !== null) {
        const shortname = match[1]?.trim() || match[2]?.trim(); // Use href path or link text
        const title = match[3]?.trim();
        const description = match[4]?.trim();

        if (shortname && title) {
            graphs.push({
                shortname,
                label: title,
                description: description || "",
                endpoint: `https://frink.apps.renci.org/${shortname}/sparql`,
            });
        }
    }

    // If we found graphs, return them; otherwise use file data
    if (graphs.length > 0) {
        console.log(`Parsed ${graphs.length} graphs from registry HTML`);
        return graphs;
    }

    // Fallback: try simpler pattern if the main one didn't work
    // eslint-disable-next-line no-useless-escape
    const simpleRowRegex = /<tr[^>]*>.*?<td[^>]*>.*?<a[^>]*href=["']kgs\/([^\/"']+)\/[^>]*>([^<]+)<\/a>.*?<td[^>]*>([^<]+)<\/td>.*?<td[^>]*>([^<]+)<\/td>/gis;
    let simpleMatch;
    while ((simpleMatch = simpleRowRegex.exec(html)) !== null) {
        const shortname = simpleMatch[1]?.trim() || simpleMatch[2]?.trim();
        const title = simpleMatch[3]?.trim();
        const description = simpleMatch[4]?.trim();

        if (shortname && title) {
            graphs.push({
                shortname,
                label: title,
                description: description || "",
                endpoint: `https://frink.apps.renci.org/${shortname}/sparql`,
            });
        }
    }

    return graphs.length > 0 ? graphs : GRAPHS_DATA;
}

/**
 * Extract shortname from registry item
 */
function extractShortname(item: any): string | null {
    if (item.shortname) return item.shortname;
    if (item.identifier) {
        // Extract shortname from identifier/URL
        // eslint-disable-next-line no-useless-escape
        const match = item.identifier.match(/kg\/([^\/]+)/);
        if (match) return match[1];
    }
    if (item.url) {
        // eslint-disable-next-line no-useless-escape
        const match = item.url.match(/kg\/([^\/]+)/);
        if (match) return match[1];
    }
    if (item["@id"]) {
        // eslint-disable-next-line no-useless-escape
        const match = item["@id"].match(/kg\/([^\/]+)/);
        if (match) return match[1];
    }
    return null;
}

/**
 * Get graph by shortname
 */
export async function getGraphByShortname(shortname: string): Promise<RegistryGraphInfo | null> {
    const graphs = await fetchGraphsFromRegistry();
    return graphs.find(g => g.shortname.toLowerCase() === shortname.toLowerCase()) || null;
}

/**
 * Clear cache and force refresh
 */
export function clearCache(): void {
    cacheTimestamp = 0;
}

/**
 * Get current cache status
 */
export function getCacheStatus(): { timestamp: number; age: number; count: number } {
    return {
        timestamp: cacheTimestamp,
        age: Date.now() - cacheTimestamp,
        count: cachedGraphs.length,
    };
}

