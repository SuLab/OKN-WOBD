import { NextResponse } from "next/server";
import { fetchGraphsFromRegistry } from "@/lib/registry/fetch";

export async function GET() {
  try {
    const graphs = await fetchGraphsFromRegistry();
    return NextResponse.json(graphs);
  } catch (error: any) {
    console.error("Error fetching graphs from registry:", error);
    return NextResponse.json(
      { error: "Failed to fetch graphs from registry" },
      { status: 500 }
    );
  }
}



