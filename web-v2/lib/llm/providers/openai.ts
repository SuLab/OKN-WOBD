import OpenAI from "openai";
import type { LLMProvider, LLMRequest, LLMResponse } from "./types";

export class OpenAIProvider implements LLMProvider {
  async complete(request: LLMRequest, apiKey: string): Promise<LLMResponse> {
    const client = new OpenAI({ apiKey });

    const response = await client.chat.completions.create({
      model: request.model,
      messages: request.messages as any,
      temperature: request.temperature ?? 0.1,
      max_tokens: request.max_tokens,
    });

    const choice = response.choices[0];
    if (!choice || !choice.message) {
      throw new Error("No response from OpenAI");
    }

    return {
      text: choice.message.content || "",
      usage: {
        input_tokens: response.usage?.prompt_tokens || 0,
        output_tokens: response.usage?.completion_tokens || 0,
        total_tokens: response.usage?.total_tokens || 0,
      },
      provider_metadata: {
        finish_reason: choice.finish_reason,
        model: response.model,
      },
    };
  }

  async testKey(apiKey: string): Promise<{ ok: boolean; provider_metadata?: Record<string, any> }> {
    try {
      const client = new OpenAI({ apiKey });
      const response = await client.chat.completions.create({
        model: "gpt-3.5-turbo",
        messages: [{ role: "user", content: "test" }],
        max_tokens: 5,
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






