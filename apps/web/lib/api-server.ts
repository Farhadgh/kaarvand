/**
 * Server-only API access: Server Components and route handlers call FastAPI
 * directly with the httpOnly access token. Never import this from a client
 * component (`next/headers` is not available there).
 */

import { cookies } from "next/headers";

import { ACCESS_COOKIE, API_BASE } from "./api-config";
import { ApiError, toApiError } from "./api-errors";

export async function serverFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const store = await cookies();
  const token = store.get(ACCESS_COOKIE)?.value;
  const response = await fetch(`${API_BASE}/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
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

export { ApiError };
