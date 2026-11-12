"""Helpers shared by the native (httpx) chat adapters.

No heavy SDK: startup stays instant and every request/response is explicit.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import Chunk
from app.providers.credentials import scrub


def proxy_of(provider: Any) -> str | None:
    """Optional per provider proxy, configured in the panel (``meta.proxy``)."""
    meta = getattr(provider, "meta", None) or {}
    value = meta.get("proxy") if isinstance(meta, dict) else None
    return str(value) if value else None


def make_client(provider: Any, *, timeout: httpx.Timeout | float) -> httpx.AsyncClient:
    """HTTP client with explicit proxy semantics.

    ``trust_env=False`` is deliberate: a machine wide proxy (very common in Iran)
    must never silently reroute model traffic. Egress is controlled per provider
    through ``meta.proxy`` instead.
    """
    proxy = proxy_of(provider)
    if proxy:
        return httpx.AsyncClient(timeout=timeout, trust_env=False, proxy=proxy)
    return httpx.AsyncClient(timeout=timeout, trust_env=False)


async def sse_events(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Yield decoded ``data:`` payloads from an SSE response."""
    async for raw_line in response.aiter_lines():
        line = raw_line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


def openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pass through tool-calling fields; the model needs them to continue a loop."""
    out: list[dict[str, Any]] = []
    for message in messages:
        item: dict[str, Any] = {"role": message.get("role", "user")}
        content = message.get("content")
        if content is None and not message.get("tool_calls"):
            content = ""
        item["content"] = content
        for key in ("tool_calls", "tool_call_id", "name"):
            if message.get(key):
                item[key] = message[key]
        out.append(item)
    return out


def anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
            continue
        converted.append(
            {
                "role": "assistant" if role == "assistant" else "user",
                "content": str(content),
            }
        )
    system = "\n\n".join(system_parts) if system_parts else None
    return system, converted


def anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function") or {}
        if not function.get("name"):
            continue
        converted.append(
            {
                "name": function["name"],
                "description": function.get("description", ""),
                "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return converted


def gemini_payload(
    messages: list[dict[str, Any]],
    *,
    temperature: float | None,
    max_tokens: int | None,
) -> dict[str, Any]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": str(content)}],
            }
        )

    body: dict[str, Any] = {"contents": contents}
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    generation: dict[str, Any] = {}
    if temperature is not None:
        generation["temperature"] = float(temperature)
    if max_tokens:
        generation["maxOutputTokens"] = int(max_tokens)
    if generation:
        body["generationConfig"] = generation
    return body


def error_from_exception(provider: Any, exc: Exception) -> Chunk:
    code = "provider.timeout" if isinstance(exc, httpx.TimeoutException) else "provider.call_failed"
    return Chunk(type="error", error_code=code, detail=scrub(provider, str(exc)))


def http_code(status_code: int) -> str:
    """Map an upstream status to a code the panel can translate.

    ``provider.http_400`` style codes told the operator nothing (and were missing
    from ``errors-fa.ts``, hence the infamous «خطای نامشخص»). Every status now
    carries a meaning; the provider's own message travels along as ``detail``.
    """
    if status_code in (401, 403):
        return "provider.auth_failed"
    if status_code == 429:
        return "provider.rate_limited"
    if 400 <= status_code < 500:
        return "provider.rejected"
    return "provider.call_failed"


def http_error(provider: Any, status_code: int, body: bytes) -> Chunk:
    detail = body.decode("utf-8", errors="replace")
    return Chunk(type="error", error_code=http_code(status_code), detail=scrub(provider, detail))



def usage_chunk(tokens_in: Any, tokens_out: Any) -> Chunk | None:
    if tokens_in is None and tokens_out is None:
        return None
    return Chunk(
        type="usage",
        tokens_in=int(tokens_in or 0),
        tokens_out=int(tokens_out or 0),
    )
