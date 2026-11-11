/** Shared between browser and server builds (no next/headers here). */

export const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
export const ACCESS_COOKIE = "ob_access";
export const REFRESH_COOKIE = "ob_refresh";
