import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, API_BASE, REFRESH_COOKIE } from "@/lib/api-config";

type Context = { params: Promise<{ path: string[] }> };

function isSecure(request: NextRequest): boolean {
  if (process.env.COOKIE_SECURE === "true") return true;
  if (process.env.COOKIE_SECURE === "false") return false;
  const proto =
    request.headers.get("x-forwarded-proto") ?? (request.nextUrl.protocol === "https:" ? "https" : "http");
  return proto.split(",")[0].trim() === "https";
}

async function forward(request: NextRequest, context: Context, method: string) {
  const { path } = await context.params;
  const target = `${API_BASE}/v1/${path.join("/")}${request.nextUrl.search}`;
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  const headers: Record<string, string> = {
    "Content-Type": request.headers.get("content-type") ?? "application/json",
    Accept: request.headers.get("accept") ?? "application/json",
  };
  if (access) headers.Authorization = `Bearer ${access}`;

  const body = method === "GET" || method === "HEAD" ? undefined : await request.text();
  let upstream = await fetch(target, { method, headers, body, cache: "no-store" });

  let rotated: { access: string; refresh: string } | null = null;

  // access token expired -> rotate once and retry (the browser never sees tokens)
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
      headers.Authorization = `Bearer ${rotated.access}`;
      upstream = await fetch(target, { method, headers, body, cache: "no-store" });
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

  const out = new NextResponse(upstream.body, { status: upstream.status });
  const contentType = upstream.headers.get("content-type");
  if (contentType) out.headers.set("content-type", contentType);
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) out.headers.set("content-disposition", disposition);
  out.headers.set("cache-control", "no-store");
  out.headers.set("x-accel-buffering", "no");

  if (rotated) {
    const secure = isSecure(request);
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

export async function GET(request: NextRequest, context: Context) {
  return forward(request, context, "GET");
}

export async function POST(request: NextRequest, context: Context) {
  return forward(request, context, "POST");
}

export async function PUT(request: NextRequest, context: Context) {
  return forward(request, context, "PUT");
}

export async function PATCH(request: NextRequest, context: Context) {
  return forward(request, context, "PATCH");
}

export async function DELETE(request: NextRequest, context: Context) {
  return forward(request, context, "DELETE");
}
