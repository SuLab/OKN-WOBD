import { NextResponse } from "next/server";
import { searchMONDOViaOLS } from "@/lib/ontology/mondo-ols";

/**
 * GET /api/tools/ontology/mondo/search?q=diabetes&limit=15
 * Returns MONDO disease terms from OLS for disease/health_conditions autocomplete.
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
    const results = await searchMONDOViaOLS(q.trim(), limit);
    return NextResponse.json({ results });
  } catch (err) {
    console.error("[API] MONDO search error:", err);
    return NextResponse.json(
      { error: "MONDO search failed" },
      { status: 500 }
    );
  }
}
