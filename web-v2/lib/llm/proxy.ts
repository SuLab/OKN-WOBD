// Server-side LLM proxy

import { OpenAIProvider } from "./providers/openai";
import { AnthropicProvider } from "./providers/anthropic";
import { GeminiProvider } from "./providers/gemini";
import type { LLMProvider, LLMRequest, LLMResponse } from "./providers/types";

const providers: Record<string, LLMProvider> = {
  openai: new OpenAIProvider(),
  anthropic: new AnthropicProvider(),
  gemini: new GeminiProvider(),
};

export async function proxyLLMCall(
  request: LLMRequest,
  apiKey: string
): Promise<LLMResponse> {
  const provider = providers[request.provider];
  if (!provider) {
    throw new Error(`Unknown provider: ${request.provider}`);
  }

  return provider.complete(request, apiKey);
}

export async function testLLMKey(
  provider: string,
  apiKey: string
): Promise<{ ok: boolean; provider_metadata?: Record<string, any> }> {
  const providerImpl = providers[provider];
  if (!providerImpl) {
    return { ok: false, provider_metadata: { error: `Unknown provider: ${provider}` } };
  }

  return providerImpl.testKey(apiKey);
}






