import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, API_BASE, REFRESH_COOKIE } from "@/lib/api-config";

export async function POST(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  if (access) {
    await fetch(`${API_BASE}/v1/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access}`,
      },
      body: JSON.stringify({ refresh_token: refresh ?? null }),
      cache: "no-store",
    }).catch(() => null);
  }

  const out = NextResponse.json({ ok: true });
  out.cookies.delete(ACCESS_COOKIE);
  out.cookies.delete(REFRESH_COOKIE);
  return out;
}
