import { NextResponse } from "next/server";
import { runStore } from "@/lib/runs/store";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const pack_id = searchParams.get("pack_id") || undefined;
    const lane = searchParams.get("lane") || undefined;
    const start = searchParams.get("start") || undefined;
    const end = searchParams.get("end") || undefined;

    const filters: any = {};
    if (pack_id) filters.pack_id = pack_id;
    if (lane) filters.lane = lane;
    if (start && end) {
      filters.date_range = { start, end };
    }

    const records = runStore.list(filters);
    return NextResponse.json(records);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to list run records" },
      { status: 500 }
    );
  }
}






