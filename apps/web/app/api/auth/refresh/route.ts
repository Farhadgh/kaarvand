import { NextResponse, type NextRequest } from "next/server";

import {
  ACCESS_COOKIE,
  API_BASE,
  REFRESH_COOKIE,
  accessMaxAge,
  safeNextPath,
} from "@/lib/api-config";

export const dynamic = "force-dynamic";

type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

/** Self-hosted installs often run plain HTTP, so follow the real request scheme. */
function isSecure(request: NextRequest): boolean {
  if (process.env.COOKIE_SECURE === "true") return true;
  if (process.env.COOKIE_SECURE === "false") return false;
  const proto =
    request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  return proto.split(",")[0].trim() === "https";
}

/** Relative Location keeps this working behind a reverse proxy on any host. */
function redirect(path: string): NextResponse {
  return new NextResponse(null, { status: 307, headers: { location: path } });
}

async function renew(refreshToken: string): Promise<TokenPair | null> {
  try {
    const response = await fetch(`${API_BASE}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as TokenPair;
  } catch {
    return null;
  }
}

/**
 * Silent session renewal. The middleware sends every request that still holds a
 * refresh cookie but no access cookie here, so a 15-minute access token never
 * turns into a logout (or, previously, an endless `/` ↔ `/login` redirect loop).
 */
export async function GET(request: NextRequest) {
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  const tokens = refresh ? await renew(refresh) : null;

  if (!tokens) {
    const out = redirect(`/login?next=${encodeURIComponent(next)}`);
    out.cookies.delete(ACCESS_COOKIE);
    out.cookies.delete(REFRESH_COOKIE);
    return out;
  }

  const secure = isSecure(request);
  const out = redirect(next);
  out.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: accessMaxAge(tokens.expires_in),
  });
  out.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return out;
}
