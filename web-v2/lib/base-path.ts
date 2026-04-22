/**
 * Subpath deployment (e.g. https://example.org/wobd).
 * Set NEXT_PUBLIC_BASE_PATH=/wobd at build time. Omit or empty for root (localhost).
 */
export const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH || "").replace(/\/$/, "");

/** Prefix a path for same-origin fetches and links. */
export function withBasePath(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (!BASE_PATH) return p;
  return `${BASE_PATH}${p}`;
}

/**
 * Absolute URL to an app path, for server-side fetch. Uses proxy headers when present.
 */
export function absoluteUrl(request: Request, path: string): string {
  const pathWithBase = withBasePath(path.startsWith("/") ? path : `/${path}`);
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto");
  const url = new URL(request.url);
  const proto = forwardedProto || url.protocol.replace(":", "");
  const origin = forwardedHost ? `${proto}://${forwardedHost}` : url.origin;
  return `${origin}${pathWithBase}`;
}
