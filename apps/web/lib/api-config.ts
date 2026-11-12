/** Shared between browser and server builds (no next/headers here). */

export const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
export const ACCESS_COOKIE = "ob_access";
export const REFRESH_COOKIE = "ob_refresh";

/** Access cookie lives one minute less than the token so it expires first. */
export function accessMaxAge(expiresIn: number | undefined): number {
  return Math.max(60, (expiresIn || 900) - 60);
}

/** Only same-origin paths may be used as a post-login destination. */
export function safeNextPath(value: string | null | undefined): string {
  if (!value) return "/";
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}
