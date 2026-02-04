import { NextResponse } from "next/server";
import { testLLMKey } from "@/lib/llm/proxy";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { provider, api_key } = body;

    if (!provider || !api_key) {
      return NextResponse.json(
        { error: "Missing 'provider' or 'api_key' parameter" },
        { status: 400 }
      );
    }

    if (!["openai", "anthropic", "gemini"].includes(provider)) {
      return NextResponse.json(
        { error: `Unknown provider: ${provider}` },
        { status: 400 }
      );
    }

    const result = await testLLMKey(provider, api_key);

    return NextResponse.json({
      ok: result.ok,
      provider_metadata: result.provider_metadata,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Key test failed" },
      { status: 500 }
    );
  }
}






