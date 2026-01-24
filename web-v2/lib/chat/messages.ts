// Chat message state management

import type { ChatMessage } from "@/types";

const STORAGE_KEY = "wobd_chat_history";

export function saveMessagesToStorage(messages: ChatMessage[]): void {
    if (typeof window === "undefined") return;
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch (error) {
        console.warn("Failed to save chat history to localStorage:", error);
    }
}

export function loadMessagesFromStorage(): ChatMessage[] {
    if (typeof window === "undefined") return [];
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return [];
        return JSON.parse(stored) as ChatMessage[];
    } catch (error) {
        console.warn("Failed to load chat history from localStorage:", error);
        return [];
    }
}

export function clearMessagesFromStorage(): void {
    if (typeof window === "undefined") return;
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
        console.warn("Failed to clear chat history from localStorage:", error);
    }
}

export function generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

