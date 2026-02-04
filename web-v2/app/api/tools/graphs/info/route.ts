import { NextResponse } from "next/server";
import { fetchGraphsFromRegistry, getGraphByShortname } from "@/lib/registry/fetch";

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const shortname = searchParams.get("shortname");

    try {
        if (shortname) {
            // Return details for a specific graph
            const graph = await getGraphByShortname(shortname);

            if (!graph) {
                // Get all graphs for error message
                const allGraphs = await fetchGraphsFromRegistry();
                return NextResponse.json(
                    {
                        error: `Graph "${shortname}" not found`,
                        available_graphs: allGraphs.map(g => g.shortname)
                    },
                    { status: 404 }
                );
            }

            // Return graph info with additional details
            return NextResponse.json({
                ...graph,
                graph_iri: `https://purl.org/okn/frink/kg/${graph.shortname}`,
                description: graph.description || `Graph shortname: ${graph.shortname}. Use this graph in SPARQL queries with: FROM <https://purl.org/okn/frink/kg/${graph.shortname}>`,
            });
        }

        // Return list of all graphs
        const graphs = await fetchGraphsFromRegistry();
        return NextResponse.json({
            graphs: graphs.map((g) => ({
                shortname: g.shortname,
                label: g.label,
                description: g.description || "",
                graph_iri: `https://purl.org/okn/frink/kg/${g.shortname}`,
            })),
            total: graphs.length,
            message: `Use @graph <shortname> to get details about a specific graph. Available graphs: ${graphs.map((g) => g.shortname).join(", ")}`,
        });
    } catch (error: any) {
        console.error("Error fetching graph info:", error);
        return NextResponse.json(
            { error: "Failed to fetch graph information from registry" },
            { status: 500 }
        );
    }
}

