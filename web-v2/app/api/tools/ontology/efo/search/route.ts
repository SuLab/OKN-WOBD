import { NextResponse } from "next/server";
import { searchEFOViaOLS } from "@/lib/ontology/efo-ols";

/**
 * GET /api/tools/ontology/efo/search?q=treatment&limit=20
 * Returns EFO terms from OLS for factor term autocomplete.
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q");
  const limitParam = searchParams.get("limit");
  const limit = limitParam ? Math.min(Math.max(parseInt(limitParam, 10) || 20, 1), 50) : 20;

  if (!q || typeof q !== "string") {
    return NextResponse.json(
      { error: "Missing or invalid query parameter 'q'" },
      { status: 400 }
    );
  }

  try {
    const results = await searchEFOViaOLS(q.trim(), limit);
    return NextResponse.json({ results });
  } catch (err) {
    console.error("[API] EFO search error:", err);
    return NextResponse.json(
      { error: "EFO search failed" },
      { status: 500 }
    );
  }
}
