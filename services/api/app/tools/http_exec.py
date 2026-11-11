"""Declarative HTTP tool execution: template + auth + response map, no code."""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import AppError
from app.providers.jsonpath import fill, resolve
from app.tools.net import ensure_domain, make_tool_client
from app.tools.secrets import decrypt_tool_secret

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}


def _apply_auth(
    headers: dict[str, Any],
    query: dict[str, Any],
    auth: dict[str, Any],
    secret: str | None,
) -> None:
    kind = str((auth or {}).get("type") or "none").lower()
    if kind == "none":
        return
    if not secret:
        raise AppError(code="tool.secret_missing", status_code=422, params={"auth": kind})
    if kind == "bearer":
        headers["Authorization"] = f"Bearer {secret}"
    elif kind == "header":
        headers[str(auth.get("header") or "X-Api-Key")] = secret
    elif kind == "query":
        query[str(auth.get("param") or "api_key")] = secret
    else:
        raise AppError(code="tool.invalid_auth", status_code=422, params={"auth": kind})


def build_request(tool: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Pure function: build the outgoing request (unit testable without network)."""
    config = tool.config or {}
    url_template = config.get("url")
    if not url_template:
        raise AppError(code="tool.missing_url", status_code=422)

    secret = decrypt_tool_secret(tool)
    variables: dict[str, Any] = {
        "base_url": config.get("base_url", ""),
        "secret": secret or "",
        **{key: value for key, value in args.items()},
    }

    url = fill(url_template, variables)
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise AppError(code="tool.invalid_url", status_code=422, params={"url": str(url)})
    ensure_domain(url, config.get("allowed_domains"))

    method = str(config.get("method") or "GET").upper()
    if method not in ALLOWED_METHODS:
        raise AppError(code="tool.method_not_allowed", status_code=422, params={"method": method})

    headers = fill(config.get("headers") or {}, variables)
    query = fill(config.get("query") or {}, variables)
    body = fill(config.get("body"), variables) if config.get("body") is not None else None

    _apply_auth(headers, query, config.get("auth") or {}, secret)

    for header_name, header_value in headers.items():
        try:
            str(header_value).encode("latin-1")
        except UnicodeEncodeError as exc:
            raise AppError(
                code="tool.invalid_header",
                status_code=422,
                params={"header": str(header_name)},
            ) from exc

    return {
        "method": method,
        "url": url,
        "headers": {str(key): str(value) for key, value in headers.items()},
        "params": {str(key): str(value) for key, value in query.items()},
        "json": body,
        "timeout": float(config.get("timeout") or 30.0),
    }


async def execute_http_tool(tool: Any, args: dict[str, Any]) -> dict[str, Any]:
    request = build_request(tool, args)
    timeout = request.pop("timeout")

    async with make_tool_client(tool.config or {}, timeout=timeout) as client:
        response = await client.request(**request)

    result: dict[str, Any] = {
        "ok": response.is_success,
        "status_code": response.status_code,
        "text": response.text[:4000],
    }

    payload: Any = None
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            payload = None
    if payload is not None:
        serialized = json.dumps(payload, ensure_ascii=False)
        result["json"] = payload if len(serialized) <= 20000 else {"_truncated": True}

    mapping = (tool.config or {}).get("response_map") or {}
    if mapping and payload is not None:
        result["mapped"] = {
            key: resolve(payload, path) for key, path in mapping.items() if isinstance(path, str)
        }
    return result
