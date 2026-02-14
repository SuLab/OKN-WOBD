import { NextResponse } from "next/server";
import { searchUBERONViaUbergraph, searchUBERONViaOLS } from "@/lib/ontology/uberon-ubergraph";

/**
 * GET /api/tools/ontology/uberon/search?q=heart&limit=20&source=ubergraph|ols
 * Returns UBERON terms for tissue autocomplete.
 * - source=ubergraph (default): FRINK Ubergraph SPARQL
 * - source=ols: OLS API (faster, ranked)
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q");
  const source = searchParams.get("source") || "ubergraph";
  const limitParam = searchParams.get("limit");
  const limit = limitParam ? Math.min(Math.max(parseInt(limitParam, 10) || 20, 1), 50) : 20;

  if (!q || typeof q !== "string") {
    return NextResponse.json(
      { error: "Missing or invalid query parameter 'q'" },
      { status: 400 }
    );
  }

  try {
    const results =
      source === "ols"
        ? await searchUBERONViaOLS(q.trim(), limit)
        : await searchUBERONViaUbergraph(q.trim(), limit);
    return NextResponse.json({ results });
  } catch (err) {
    console.error("[API] UBERON search error:", err);
    return NextResponse.json(
      { error: "UBERON search failed" },
      { status: 500 }
    );
  }
}
