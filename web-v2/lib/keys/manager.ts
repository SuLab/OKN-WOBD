// BYOK key management (session-based)

import type { Provider } from "@/lib/llm/providers/types";

interface KeyStorage {
  getKey(provider: Provider, sessionId: string): string | null;
  setKey(provider: Provider, sessionId: string, key: string): void;
  removeKey(provider: Provider, sessionId: string): void;
  clearSession(sessionId: string): void;
}

// In-memory storage (in production, use Redis or database)
class MemoryKeyStorage implements KeyStorage {
  private keys: Map<string, string> = new Map();

  private getKey(provider: Provider, sessionId: string): string | null {
    return this.keys.get(`${sessionId}:${provider}`) || null;
  }

  private setKey(provider: Provider, sessionId: string, key: string): void {
    this.keys.set(`${sessionId}:${provider}`, key);
  }

  private removeKey(provider: Provider, sessionId: string): void {
    this.keys.delete(`${sessionId}:${provider}`);
  }

  private clearSession(sessionId: string): void {
    const keysToDelete: string[] = [];
    for (const key of this.keys.keys()) {
      if (key.startsWith(`${sessionId}:`)) {
        keysToDelete.push(key);
      }
    }
    for (const key of keysToDelete) {
      this.keys.delete(key);
    }
  }
}

const storage: KeyStorage = new MemoryKeyStorage();

export function getBYOKKey(provider: Provider, sessionId: string): string | null {
  return storage.getKey(provider, sessionId);
}

export function setBYOKKey(provider: Provider, sessionId: string, key: string): void {
  storage.setKey(provider, sessionId, key);
}

export function removeBYOKKey(provider: Provider, sessionId: string): void {
  storage.removeKey(provider, sessionId);
}

export function clearSessionKeys(sessionId: string): void {
  storage.clearSession(sessionId);
}






