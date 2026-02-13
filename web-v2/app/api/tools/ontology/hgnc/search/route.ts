import { NextResponse } from "next/server";
import { searchHGNCForAutocomplete } from "@/lib/ontology/hgnc-client";

/**
 * GET /api/tools/ontology/hgnc/search?q=DUSP&limit=15
 * Returns HGNC gene results (symbol, name) for gene symbol/name autocomplete.
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q");
  const limitParam = searchParams.get("limit");
  const limit = limitParam ? Math.min(Math.max(parseInt(limitParam, 10) || 15, 1), 50) : 15;

  if (!q || typeof q !== "string") {
    return NextResponse.json(
      { error: "Missing or invalid query parameter 'q'" },
      { status: 400 }
    );
  }

  try {
    const results = await searchHGNCForAutocomplete(q.trim(), limit);
    return NextResponse.json({ results });
  } catch (err) {
    console.error("[API] HGNC search error:", err);
    return NextResponse.json(
      { error: "HGNC search failed" },
      { status: 500 }
    );
  }
}
