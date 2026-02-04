import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";
import type { Intent } from "@/types";
import { generateSPARQLFromIntent } from "@/lib/templates/generator";

// Lane A: Template-based SPARQL generation from intent + context pack
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { intent, pack_id } = body as { intent: Intent; pack_id?: string };

    if (!intent || typeof intent !== "object") {
      return NextResponse.json(
        { error: "Missing or invalid 'intent' parameter" },
        { status: 400 }
      );
    }

    const pack = pack_id ? loadContextPack(pack_id) : null;
    if (pack_id && !pack) {
      return NextResponse.json(
        { error: `Context pack not found: ${pack_id}` },
        { status: 404 }
      );
    }

    const resolvedPack = pack || loadContextPack("wobd");
    if (!resolvedPack) {
      return NextResponse.json(
        { error: "No context pack available (requested pack not found and default 'wobd' missing)" },
        { status: 500 }
      );
    }

    const result = await generateSPARQLFromIntent(intent, resolvedPack);
    if (!result.ok || !result.query) {
      return NextResponse.json(
        { error: result.error || "Failed to generate SPARQL from intent" },
        { status: 400 }
      );
    }

    return NextResponse.json({ query: result.query });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "SPARQL generation failed" },
      { status: 500 }
    );
  }
}

