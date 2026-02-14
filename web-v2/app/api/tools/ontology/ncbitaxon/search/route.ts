import { NextResponse } from "next/server";
import { searchNCBITaxonViaOLS } from "@/lib/ontology/ncbitaxon-ols";

/**
 * GET /api/tools/ontology/ncbitaxon/search?q=mouse&limit=20
 * Returns NCBITaxon terms from OLS for organism autocomplete.
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
    const results = await searchNCBITaxonViaOLS(q.trim(), limit);
    return NextResponse.json({ results });
  } catch (err) {
    console.error("[API] NCBITaxon search error:", err);
    return NextResponse.json(
      { error: "NCBITaxon search failed" },
      { status: 500 }
    );
  }
}
