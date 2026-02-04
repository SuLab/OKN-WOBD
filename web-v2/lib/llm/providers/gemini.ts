import { GoogleGenerativeAI } from "@google/generative-ai";
import type { LLMProvider, LLMRequest, LLMResponse } from "./types";

export class GeminiProvider implements LLMProvider {
  async complete(request: LLMRequest, apiKey: string): Promise<LLMResponse> {
    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({ model: request.model });

    // Convert messages format for Gemini
    const systemMessage = request.messages.find(m => m.role === "system");
    const conversationMessages = request.messages.filter(m => m.role !== "system");

    // Build prompt with system message if present
    let prompt = "";
    if (systemMessage) {
      prompt += `${systemMessage.content}\n\n`;
    }

    // Add conversation history
    for (const msg of conversationMessages) {
      if (msg.role === "user") {
        prompt += `User: ${msg.content}\n`;
      } else if (msg.role === "assistant") {
        prompt += `Assistant: ${msg.content}\n`;
      }
    }

    const result = await model.generateContent({
      contents: [{ role: "user", parts: [{ text: prompt }] }] as any,
      generationConfig: {
        temperature: request.temperature ?? 0.1,
        maxOutputTokens: request.max_tokens,
      },
    });

    const response = result.response;
    const text = response.text();

    // Gemini doesn't provide token usage in the same way
    // Estimate based on text length (rough approximation)
    const estimatedInputTokens = Math.ceil(prompt.length / 4);
    const estimatedOutputTokens = Math.ceil(text.length / 4);

    return {
      text,
      usage: {
        input_tokens: estimatedInputTokens,
        output_tokens: estimatedOutputTokens,
        total_tokens: estimatedInputTokens + estimatedOutputTokens,
      },
      provider_metadata: {
        finish_reason: response.candidates?.[0]?.finishReason,
        model: request.model,
      },
    };
  }

  async testKey(apiKey: string): Promise<{ ok: boolean; provider_metadata?: Record<string, any> }> {
    try {
      const genAI = new GoogleGenerativeAI(apiKey);
      const model = genAI.getGenerativeModel({ model: "gemini-pro" });
      const result = await model.generateContent("test");
      await result.response;
      return {
        ok: true,
        provider_metadata: {
          model: "gemini-pro",
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






