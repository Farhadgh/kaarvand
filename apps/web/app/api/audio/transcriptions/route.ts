import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, API_BASE, REFRESH_COOKIE } from "@/lib/api-config";

/**
 * Binary-safe proxy for audio uploads.
 *
 * The generic `/api/[...path]` proxy reads the body with `request.text()`, which
 * would destroy a multipart payload. This route forwards the raw bytes and keeps
 * the original `content-type` (with its boundary) so STT uploads work.
 */
export async function POST(request: NextRequest) {
  const target = `${API_BASE}/v1/audio/transcriptions`;
  const body = await request.arrayBuffer();
  const contentType = request.headers.get("content-type") ?? "application/octet-stream";
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  const send = async (token: string | undefined) => {
    const headers: Record<string, string> = { "Content-Type": contentType, Accept: "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(target, { method: "POST", headers, body, cache: "no-store" });
  };

  let upstream = await send(access);
  let rotated: { access: string; refresh: string } | null = null;

  if (upstream.status === 401 && refresh) {
    const refreshed = await fetch(`${API_BASE}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (refreshed.ok) {
      const tokens = (await refreshed.json()) as { access_token: string; refresh_token: string };
      rotated = { access: tokens.access_token, refresh: tokens.refresh_token };
      upstream = await send(rotated.access);
    } else if (refreshed.status === 401) {
      const out = NextResponse.json(
        { error: { code: "auth.session_expired", params: {} } },
        { status: 401 },
      );
      out.cookies.delete(ACCESS_COOKIE);
      out.cookies.delete(REFRESH_COOKIE);
      return out;
    }
  }

  const payload = await upstream.text();
  const out = new NextResponse(payload, { status: upstream.status });
  out.headers.set("content-type", upstream.headers.get("content-type") ?? "application/json");
  out.headers.set("cache-control", "no-store");

  if (rotated) {
    const secure = (request.headers.get("x-forwarded-proto") ?? "http").split(",")[0].trim() === "https";
    out.cookies.set(ACCESS_COOKIE, rotated.access, {
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/",
      maxAge: 60 * 60,
    });
    out.cookies.set(REFRESH_COOKIE, rotated.refresh, {
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/",
      maxAge: 60 * 60 * 24 * 7,
    });
  }

  return out;
}
