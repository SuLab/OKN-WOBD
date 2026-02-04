import Anthropic from "@anthropic-ai/sdk";
import type { LLMProvider, LLMRequest, LLMResponse } from "./types";

export class AnthropicProvider implements LLMProvider {
  async complete(request: LLMRequest, apiKey: string): Promise<LLMResponse> {
    const client = new Anthropic({ apiKey });

    // Convert messages format for Anthropic
    const systemMessage = request.messages.find(m => m.role === "system");
    const userMessages = request.messages.filter(m => m.role !== "system");

    const response = await client.messages.create({
      model: request.model,
      max_tokens: request.max_tokens || 4096,
      temperature: request.temperature ?? 0.1,
      system: systemMessage?.content,
      messages: userMessages.map(m => ({
        role: m.role === "assistant" ? "assistant" : "user",
        content: m.content,
      })) as any,
    });

    const text = response.content
      .filter((c: any) => c.type === "text")
      .map((c: any) => c.text)
      .join("");

    return {
      text,
      usage: {
        input_tokens: response.usage.input_tokens,
        output_tokens: response.usage.output_tokens,
        total_tokens: response.usage.input_tokens + response.usage.output_tokens,
      },
      provider_metadata: {
        stop_reason: response.stop_reason,
        model: response.model,
      },
    };
  }

  async testKey(apiKey: string): Promise<{ ok: boolean; provider_metadata?: Record<string, any> }> {
    try {
      const client = new Anthropic({ apiKey });
      const response = await client.messages.create({
        model: "claude-3-haiku-20240307",
        max_tokens: 5,
        messages: [{ role: "user", content: "test" }],
      });
      return {
        ok: true,
        provider_metadata: {
          model: response.model,
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        provider_metadata: {
          error: error.message,
        },
      };
    }
  }
}






