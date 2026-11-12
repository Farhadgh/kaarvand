import { NextResponse, type NextRequest } from "next/server";

const ACCESS_COOKIE = "ob_access";
const REFRESH_COOKIE = "ob_refresh";

/**
 * Session gate.
 *
 * - Access cookie missing but refresh cookie present → hand the request to
 *   `/api/auth/refresh`, which renews the pair and bounces back. Without this the
 *   15-minute access token logged every user out mid-session.
 * - Nothing at all → `/login?next=…`.
 * - `/login` bounces to the panel only when an access cookie exists **and** the
 *   visitor was not just sent here (`?next=`). Bouncing unconditionally made
 *   `/` and `/login` redirect into each other forever (stale refresh cookie +
 *   rejected access token = blank page / ERR_TOO_MANY_REDIRECTS).
 * - An access cookie the API rejects is handled by the panel layout, which sends
 *   the browser to `/api/auth/expired` to clear both cookies.
 */
export function middleware(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  const { pathname, search } = request.nextUrl;
  const isAuthPage = pathname === "/login";

  if (isAuthPage) {
    if (access && !request.nextUrl.searchParams.has("next")) {
      const url = request.nextUrl.clone();
      url.pathname = "/";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (access) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = refresh ? "/api/auth/refresh" : "/login";
  url.search = `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)"],
};

