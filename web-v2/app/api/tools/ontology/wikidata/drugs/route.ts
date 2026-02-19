import { NextResponse } from "next/server";
import { searchWikidataDrugs } from "@/lib/ontology/wikidata-client";

/**
 * GET /api/tools/ontology/wikidata/drugs?q=aspirin&limit=15
 * Returns Wikidata drug results (label, description, wikidata_id) for drug autocomplete.
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q");
  const limitParam = searchParams.get("limit");
  const limit = limitParam ? Math.min(Math.max(parseInt(limitParam, 10) || 15, 1), 25) : 15;

  if (!q || typeof q !== "string") {
    return NextResponse.json(
      { error: "Missing or invalid query parameter 'q'" },
      { status: 400 }
    );
  }

  const trimmed = q.trim();
  if (trimmed.length < 2) {
    return NextResponse.json({ results: [] });
  }

  try {
    const results = await searchWikidataDrugs(trimmed);
    const slice = results.slice(0, limit).map((r) => ({
      label: r.label,
      wikidata_id: r.wikidata_id,
      wikidata_iri: r.wikidata_iri,
      description: r.description ?? undefined,
    }));
    return NextResponse.json({ results: slice });
  } catch (err) {
    console.error("[API] Wikidata drug search error:", err);
    return NextResponse.json(
      { error: "Wikidata drug search failed" },
      { status: 500 }
    );
  }
}
