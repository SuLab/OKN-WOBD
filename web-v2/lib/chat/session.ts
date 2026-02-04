// Frontend session management for API key BYOK system
// Stores session_id in localStorage to persist across page reloads

const SESSION_ID_KEY = "wobd_session_id";

/**
 * Get or create a session ID for BYOK API key management.
 * 
 * The session ID is stored in localStorage and persists across page reloads.
 * If no session ID exists, a new one is generated using a simple UUID-like format.
 * 
 * @returns The session ID string
 */
export function getSessionId(): string {
    if (typeof window === "undefined") {
        // Server-side: return a temporary ID (shouldn't happen in practice)
        return "server-session";
    }

    // Try to get existing session ID from localStorage
    const existing = localStorage.getItem(SESSION_ID_KEY);
    if (existing) {
        return existing;
    }

    // Generate a new session ID (simple UUID-like format)
    const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    localStorage.setItem(SESSION_ID_KEY, newSessionId);
    return newSessionId;
}

/**
 * Clear the stored session ID.
 * Useful for logging out or resetting the session.
 */
export function clearSessionId(): void {
    if (typeof window !== "undefined") {
        localStorage.removeItem(SESSION_ID_KEY);
    }
}

/**
 * Check if a session ID exists.
 * @returns true if a session ID is stored
 */
export function hasSessionId(): boolean {
    if (typeof window === "undefined") {
        return false;
    }
    return localStorage.getItem(SESSION_ID_KEY) !== null;
}
