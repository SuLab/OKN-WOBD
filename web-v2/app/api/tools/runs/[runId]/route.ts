import { NextResponse } from "next/server";
import { runStore } from "@/lib/runs/store";

export async function GET(
  request: Request,
  { params }: { params: { runId: string } }
) {
  try {
    const record = runStore.get(params.runId);
    if (!record) {
      return NextResponse.json(
        { error: `Run record not found: ${params.runId}` },
        { status: 404 }
      );
    }
    return NextResponse.json(record);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to retrieve run record" },
      { status: 500 }
    );
  }
}






