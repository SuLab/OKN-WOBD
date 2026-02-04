import { NextResponse } from "next/server";
import { getHardcodedSuggestions } from "@/lib/registry/suggestions";
import { fetchGraphsFromRegistry, getGraphByShortname } from "@/lib/registry/fetch";

/**
 * GET /api/tools/registry/graphs/suggestions?graphs=nde
 * Returns hardcoded categorized imperative suggestions (Find..., Show me..., Which...).
 * No subtext; one line per query; grouped by Dataset Discovery, Genes & Diseases, etc.
 */
export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const graphsParam = searchParams.get("graphs");

    try {
        const categories = getHardcodedSuggestions();
        const total = categories.reduce((n, c) => n + c.queries.length, 0);

        if (!graphsParam) {
            const allGraphs = await fetchGraphsFromRegistry();
            return NextResponse.json({
                categories,
                total,
                graphs: allGraphs.map(g => g.shortname),
            });
        }

        const graphShortnames = graphsParam.split(",").map(s => s.trim()).filter(Boolean);
        if (graphShortnames.length === 0) {
            return NextResponse.json(
                { error: "No graphs specified" },
                { status: 400 }
            );
        }

        const graphs = [];
        for (const shortname of graphShortnames) {
            const graph = await getGraphByShortname(shortname);
            if (!graph) {
                return NextResponse.json(
                    { error: `Graph "${shortname}" not found` },
                    { status: 404 }
                );
            }
            graphs.push(graph);
        }

        return NextResponse.json({
            categories,
            total,
            graphs: graphShortnames,
            ...(graphShortnames.length === 1 && { graphLabel: graphs[0].label }),
        });
    } catch (error: any) {
        console.error("Error getting graph suggestions:", error);
        return NextResponse.json(
            { error: error.message || "Failed to get suggestions" },
            { status: 500 }
        );
    }
}

