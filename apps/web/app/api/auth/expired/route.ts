import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, safeNextPath } from "@/lib/api-config";

export const dynamic = "force-dynamic";

/**
 * Cookie reset endpoint. The panel layout sends a 401 (a cookie the API rejects,
 * e.g. after a JWT secret change) here so the stale pair is dropped and the
 * browser lands on `/login` instead of ping-ponging between `/` and `/login`.
 */
export async function GET(request: NextRequest) {
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));
  const out = new NextResponse(null, {
    status: 307,
    headers: { location: `/login?next=${encodeURIComponent(next)}` },
  });
  out.cookies.delete(ACCESS_COOKIE);
  out.cookies.delete(REFRESH_COOKIE);
  return out;
}
