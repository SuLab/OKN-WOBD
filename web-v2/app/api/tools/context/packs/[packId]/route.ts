import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";

export async function GET(
  request: Request,
  { params }: { params: { packId: string } }
) {
  try {
    const pack = loadContextPack(params.packId);
    if (!pack) {
      return NextResponse.json(
        { error: `Context pack not found: ${params.packId}` },
        { status: 404 }
      );
    }
    return NextResponse.json(pack);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to load context pack" },
      { status: 500 }
    );
  }
}






