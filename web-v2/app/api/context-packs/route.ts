import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";

export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const packId = searchParams.get("pack_id") || "wobd";

        const pack = loadContextPack(packId);

        if (!pack) {
            return NextResponse.json(
                { error: `Context pack not found: ${packId}` },
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
