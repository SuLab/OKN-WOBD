import { NextResponse } from "next/server";
import { listPacks } from "@/lib/context-packs/loader";

export async function GET() {
  try {
    const packs = listPacks();
    return NextResponse.json(packs.map(p => ({
      id: p.id,
      label: p.label,
      description: p.description,
      version: p.version,
    })));
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to load context packs" },
      { status: 500 }
    );
  }
}






