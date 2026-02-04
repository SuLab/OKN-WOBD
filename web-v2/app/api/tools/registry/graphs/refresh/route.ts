import { NextResponse } from "next/server";
import { fetchGraphsFromRegistry, clearCache, getCacheStatus } from "@/lib/registry/fetch";

/**
 * Manual refresh endpoint for registry graphs
 * POST /api/tools/registry/graphs/refresh
 * 
 * Forces a refresh from the OKN Registry and updates the graphs.ts file
 */
export async function POST() {
    try {
        // Clear cache to force refresh
        clearCache();

        // Fetch from registry (force refresh)
        const graphs = await fetchGraphsFromRegistry(true);

        const status = getCacheStatus();

        return NextResponse.json({
            success: true,
            message: `Refreshed ${graphs.length} graphs from OKN Registry`,
            count: graphs.length,
            timestamp: new Date(status.timestamp).toISOString(),
            graphs: graphs.map(g => ({
                shortname: g.shortname,
                label: g.label,
                description: g.description || "",
            })),
        });
    } catch (error: any) {
        console.error("Error refreshing graphs:", error);
        return NextResponse.json(
            {
                success: false,
                error: error.message || "Failed to refresh graphs from registry"
            },
            { status: 500 }
        );
    }
}

/**
 * GET endpoint to check cache status
 */
export async function GET() {
    try {
        const status = getCacheStatus();
        const ageHours = Math.floor(status.age / (1000 * 60 * 60));
        const ageMinutes = Math.floor((status.age % (1000 * 60 * 60)) / (1000 * 60));

        return NextResponse.json({
            cached: status.count > 0,
            count: status.count,
            lastUpdated: status.timestamp > 0 ? new Date(status.timestamp).toISOString() : null,
            age: {
                hours: ageHours,
                minutes: ageMinutes,
                total_ms: status.age,
            },
            nextRefresh: status.timestamp > 0
                ? new Date(status.timestamp + 24 * 60 * 60 * 1000).toISOString()
                : null,
        });
    } catch (_error: any) {
        return NextResponse.json(
            { error: "Failed to get cache status" },
            { status: 500 }
        );
    }
}

