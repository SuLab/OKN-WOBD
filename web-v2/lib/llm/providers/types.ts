// LLM provider abstraction interface

export type Provider = "openai" | "anthropic" | "gemini";

export interface LLMRequest {
  provider: Provider;
  model: string;
  messages: Array<{ role: "system" | "user" | "assistant"; content: string }>;
  temperature?: number;
  max_tokens?: number;
}

export interface LLMResponse {
  text: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  provider_metadata?: Record<string, any>;
}

export interface LLMProvider {
  complete(request: LLMRequest, apiKey: string): Promise<LLMResponse>;
  testKey(apiKey: string): Promise<{ ok: boolean; provider_metadata?: Record<string, any> }>;
}






