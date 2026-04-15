import { NextResponse } from "next/server";
import {
    fetchGraphsFromRegistry,
    clearCache,
    getCacheStatus,
    USE_STATIC_GRAPH_LIST,
} from "@/lib/registry/fetch";

/**
 * POST /api/tools/registry/graphs/refresh
 * Reloads graph list: from ./graphs when USE_STATIC_GRAPH_LIST is true; otherwise from OKN Registry (and may update graphs files).
 */
export async function POST() {
    try {
        clearCache();
        const graphs = await fetchGraphsFromRegistry(true);

        const status = getCacheStatus();

        return NextResponse.json({
            success: true,
            message: USE_STATIC_GRAPH_LIST
                ? `Reloaded ${graphs.length} graphs from static graph list`
                : `Refreshed ${graphs.length} graphs from OKN Registry`,
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
                error: error.message || (USE_STATIC_GRAPH_LIST
                    ? "Failed to reload graph list"
                    : "Failed to refresh graphs from registry")
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
            nextRefresh: USE_STATIC_GRAPH_LIST
                ? null
                : status.timestamp > 0
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

