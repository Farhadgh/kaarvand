import { NextResponse, type NextRequest } from "next/server";

const ACCESS_COOKIE = "ob_access";
const REFRESH_COOKIE = "ob_refresh";

export function middleware(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  const { pathname, search } = request.nextUrl;
  const isAuthPage = pathname === "/login";

  if (!access && !refresh && !isAuthPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  if ((access || refresh) && isAuthPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)"],
};
