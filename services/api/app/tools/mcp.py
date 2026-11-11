"""Minimal MCP client (JSON-RPC 2.0 over HTTP, SSE aware)."""

from __future__ import annotations

import json
from itertools import count
from typing import Any

from app.core.errors import AppError
from app.tools.net import make_tool_client

_ids = count(1)
PROTOCOL_VERSION = "2025-06-18"


async def _rpc(server: Any, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not server.url:
        raise AppError(code="mcp.missing_url", status_code=422)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if server.auth_enc:
        from app.core.crypto import get_secret_box

        token = get_secret_box().decrypt(server.auth_enc, aad=f"mcp:{server.id}")
        headers["Authorization"] = f"Bearer {token}"

    body = {
        "jsonrpc": "2.0",
        "id": next(_ids),
        "method": method,
        "params": params or {},
    }

    async with make_tool_client({}, timeout=30.0) as client:
        response = await client.post(str(server.url), headers=headers, json=body)

    if response.status_code >= 400:
        raise AppError(
            code="mcp.http_error",
            status_code=502,
            params={"status": response.status_code, "detail": response.text[:300]},
        )

    payload: dict[str, Any] | None = None
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                candidate = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and ("result" in candidate or "error" in candidate):
                payload = candidate
                break
    else:
        try:
            payload = response.json()
        except ValueError:
            payload = None

    if payload is None:
        raise AppError(code="mcp.invalid_response", status_code=502)

    if "error" in payload:
        error = payload["error"] or {}
        raise AppError(
            code="mcp.rpc_error",
            status_code=502,
            params={
                "rpc_code": error.get("code"),
                "message": str(error.get("message") or "")[:300],
                "method": method,
            },
        )
    return payload


async def initialize(server: Any) -> dict[str, Any]:
    return await _rpc(
        server,
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "kaarvand", "version": "0.1.0"},
        },
    )


async def list_tools(server: Any) -> list[dict[str, Any]]:
    payload = await _rpc(server, "tools/list", {})
    result = payload.get("result") or {}
    tools = result.get("tools") or []
    return [tool for tool in tools if isinstance(tool, dict)]


async def call_tool(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = await _rpc(server, "tools/call", {"name": name, "arguments": arguments})
    result = payload.get("result") or {}
    return result if isinstance(result, dict) else {"content": result}
