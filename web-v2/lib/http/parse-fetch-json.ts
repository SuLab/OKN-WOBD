/**
 * Safe parsing of fetch Response bodies that are expected to be JSON.
 * Avoids SyntaxError from response.json() when proxies return HTML (502/504 pages).
 */

function trimPreview(text: string, maxLen: number): string {
  return text.trim().replace(/\s+/g, " ").slice(0, maxLen);
}

function bodyLooksLikeHtml(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (/^<!doctype\s+html/i.test(t) || /^<html[\s>]/i.test(t)) return true;
  if (t.startsWith("<") && !/^\s*[\[{]/.test(t)) return true;
  return false;
}

/**
 * Parse JSON from a response body string. Use after reading response.text().
 * @throws Error with context when body is empty, HTML, or not valid JSON.
 */
export function parseJsonOrThrow<T>(bodyText: string, response: Response, context: string): T {
  const t = bodyText.trim();
  const { status, statusText } = response;
  if (!t) {
    throw new Error(`${context}: empty response body (HTTP ${status} ${statusText}).`);
  }
  if (bodyLooksLikeHtml(bodyText)) {
    throw new Error(
      `${context}: HTTP ${status} ${statusText} — body was HTML, not JSON (often a reverse-proxy 502/504). Preview: ${trimPreview(t, 200)}…`,
    );
  }
  try {
    return JSON.parse(bodyText) as T;
  } catch {
    throw new Error(
      `${context}: invalid JSON (HTTP ${status} ${statusText}). Preview: ${trimPreview(t, 200)}…`,
    );
  }
}

/**
 * Human-readable message for a failed HTTP response body (non-OK or caller-defined).
 * Use when you should return an error string instead of throwing (e.g. dashboard UI).
 */
export function errorMessageFromFailedApiBody(
  response: Response,
  bodyText: string,
  context: string
): string {
  const t = bodyText.trim();
  const { status, statusText } = response;
  if (!t) {
    return `${context}: HTTP ${status} ${statusText} (empty body).`;
  }
  if (bodyLooksLikeHtml(bodyText)) {
    return `${context}: HTTP ${status} ${statusText} — body was HTML, not JSON (often a reverse-proxy or gateway timeout). Preview: ${trimPreview(t, 200)}…`;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(bodyText);
  } catch {
    return `${context}: HTTP ${status} ${statusText} — invalid JSON. Preview: ${trimPreview(t, 200)}…`;
  }
  if (parsed && typeof parsed === "object" && "error" in parsed) {
    const err = (parsed as { error?: unknown }).error;
    if (typeof err === "string" && err.trim()) {
      return err.trim();
    }
  }
  return `${context}: HTTP ${status} ${statusText}.`;
}

/**
 * For a non-OK HTTP response whose body was already read as text.
 * Prefers JSON `{ "error": "..." }` when present; otherwise explains HTML/plain failures.
 * @throws Always (return type never).
 */
export function throwForFailedApiResponseWithBody(
  response: Response,
  bodyText: string,
  context: string
): never {
  throw new Error(errorMessageFromFailedApiBody(response, bodyText, context));
}
