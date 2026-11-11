import { NextResponse } from "next/server";

import { ACCESS_COOKIE, API_BASE, REFRESH_COOKIE } from "@/lib/api-config";

/** Self-hosted installs often run plain HTTP, so follow the real request scheme. */
function isSecure(request: Request): boolean {
  if (process.env.COOKIE_SECURE === "true") return true;
  if (process.env.COOKIE_SECURE === "false") return false;
  const proto =
    request.headers.get("x-forwarded-proto") ??
    (request.url.startsWith("https:") ? "https" : "http");
  return proto.split(",")[0].trim() === "https";
}

export async function POST(request: Request) {
  const secure = isSecure(request);
  const payload = await request.json().catch(() => ({}));

  const response = await fetch(`${API_BASE}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return NextResponse.json(data, { status: response.status });
  }

  const out = NextResponse.json({ user: data.user });
  out.cookies.set(ACCESS_COOKIE, data.access_token as string, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60,
  });
  out.cookies.set(REFRESH_COOKIE, data.refresh_token as string, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return out;
}
