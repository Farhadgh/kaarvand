/**
 * Browser-side API access.
 *
 * Client components never talk to FastAPI directly: they use the BFF at
 * `/api/*`, which forwards the httpOnly cookie, re-attaches the bearer token
 * and transparently rotates an expired access token.
 *
 * Server Components must import `serverFetch` from `@/lib/api-server` instead.
 */

import { toApiError } from "./api-errors";

export { ApiError, messageOf, toApiError } from "./api-errors";
export { ACCESS_COOKIE, API_BASE, REFRESH_COOKIE } from "./api-config";

/** Client side: go through the BFF proxy at /api/*. */
export async function clientFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    credentials: "same-origin",
  });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw toApiError(response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Client side SSE: parses `data: {event, data}` frames from the proxy. */
export async function clientStream(
  path: string,
  body: unknown,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });

  if (!response.ok || !response.body) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw toApiError(response.status, payload);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          const parsed = JSON.parse(raw) as { event?: string; data?: Record<string, unknown> };
          if (parsed.event) onEvent(parsed.event, parsed.data ?? {});
        } catch {
          // ignore malformed frame
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export function buildQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}
