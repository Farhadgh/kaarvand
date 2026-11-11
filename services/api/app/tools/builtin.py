"""Builtin tools shipped with the platform (no external app required)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.core.errors import AppError
from app.core.jalali import format_jalali_long, now_in, today_jalali
from app.providers.adapters.chat_common import make_client


async def system_now_jalali(args: dict[str, Any], tool: Any) -> dict[str, Any]:
    timezone = str(args.get("timezone") or "Asia/Tehran")
    now = now_in(timezone)
    return {
        "timezone": timezone,
        "iso": now.isoformat(),
        "jalali": format_jalali_long(now),
        "jalali_short": today_jalali(timezone),
    }


def _domain_allowed(url: str, allowed: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    for candidate in allowed:
        entry = candidate.lower().strip()
        if not entry:
            continue
        if host == entry or host.endswith(f".{entry}"):
            return True
    return False


async def http_request(args: dict[str, Any], tool: Any) -> dict[str, Any]:
    """Generic HTTP call, restricted to the domains configured on the tool."""
    config = tool.config or {}
    allowed = list(config.get("allowed_domains") or [])
    url = str(args.get("url") or "")
    if not allowed:
        raise AppError(code="tool.domain_not_configured", status_code=422)
    if not _domain_allowed(url, allowed):
        raise AppError(
            code="tool.domain_not_allowed",
            status_code=403,
            params={"url": url, "allowed": allowed},
        )

    method = str(args.get("method") or "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise AppError(code="tool.method_not_allowed", status_code=422, params={"method": method})

    async with make_client(tool, timeout=30.0) as client:
        response = await client.request(
            method,
            url,
            headers=args.get("headers") or {},
            json=args.get("body") if method != "GET" else None,
        )
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "text": response.text[:4000],
    }


BUILTINS = {
    "system.now_jalali": system_now_jalali,
    "http.request": http_request,
}


async def run_builtin(slug: str, args: dict[str, Any], tool: Any) -> dict[str, Any]:
    handler = BUILTINS.get(slug)
    if handler is None:
        raise AppError(code="tool.unknown_builtin", status_code=422, params={"slug": slug})
    return await handler(args, tool)
