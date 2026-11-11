"""HTTP helpers shared by tool executors (explicit proxy, domain allowlist)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.errors import AppError


def domain_allowed(url: str, allowed: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    for candidate in allowed:
        entry = str(candidate).lower().strip()
        if not entry:
            continue
        if host == entry or host.endswith(f".{entry}"):
            return True
    return False


def ensure_domain(url: str, allowed: list[str] | None) -> None:
    if not allowed:
        raise AppError(code="tool.domain_not_configured", status_code=422)
    if not domain_allowed(url, allowed):
        raise AppError(
            code="tool.domain_not_allowed",
            status_code=403,
            params={"url": url, "allowed": [str(item) for item in allowed]},
        )


def make_tool_client(config: dict[str, Any], *, timeout: float = 30.0) -> httpx.AsyncClient:
    proxy = (config or {}).get("proxy")
    if proxy:
        return httpx.AsyncClient(timeout=timeout, trust_env=False, proxy=str(proxy))
    return httpx.AsyncClient(timeout=timeout, trust_env=False)
