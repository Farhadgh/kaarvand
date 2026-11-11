"""Native Google Gemini adapter (streamGenerateContent + SSE)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.adapters.chat_common import (
    error_from_exception,
    gemini_payload,
    http_error,
    make_client,
    sse_events,
    usage_chunk,
)
from app.providers.adapters.litellm_catalog import fetch_prices, list_models, test_connection
from app.providers.adapters.litellm_endpoints import base_url, build_headers
from app.providers.base import Chunk, ConnectionResult, RemoteModel, RemotePrice
from app.providers.credentials import decrypt_api_key


class GeminiAdapter:
    kind = "gemini"

    async def list_models(self, provider: Any) -> list[RemoteModel]:
        return await list_models(provider)

    async def fetch_prices(self, provider: Any) -> list[RemotePrice]:
        return await fetch_prices(provider)

    async def test(self, provider: Any, *, timeout: float = 20.0) -> ConnectionResult:
        return await test_connection(provider, timeout=timeout)

    async def stream_chat(
        self,
        provider: Any,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[Chunk]:
        base = base_url(provider)
        if not base:
            yield Chunk(type="error", error_code="provider.missing_base_url")
            return

        api_key = decrypt_api_key(provider)
        body = gemini_payload(messages, temperature=temperature, max_tokens=max_tokens)
        if tools:
            body["tools"] = [{"functionDeclarations": _function_declarations(tools)}]

        timeout = httpx.Timeout(180.0, connect=20.0)
        try:
            async with make_client(provider, timeout=timeout) as client:
                request = client.stream(
                    "POST",
                    f"{base}/models/{model}:streamGenerateContent",
                    headers=build_headers(provider, api_key),
                    params={"alt": "sse", "key": api_key or ""},
                    json=body,
                )
                async with request as response:
                    if response.status_code >= 400:
                        yield http_error(provider, response.status_code, await response.aread())
                        return
                    async for event in sse_events(response):
                        for chunk in _parse_event(event):
                            yield chunk
        except Exception as exc:  # noqa: BLE001
            yield error_from_exception(provider, exc)
            return

        yield Chunk(type="done")


def _function_declarations(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function") or {}
        if not function.get("name"):
            continue
        declarations.append(
            {
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters": function.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return declarations


def _parse_event(event: dict[str, Any]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for candidate in event.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            if part.get("text"):
                chunks.append(Chunk(type="text", text=str(part["text"])))
            function_call = part.get("functionCall")
            if function_call:
                chunks.append(
                    Chunk(
                        type="tool_call",
                        tool_call={
                            "name": function_call.get("name"),
                            "arguments": str(function_call.get("args") or {}),
                        },
                    )
                )
    usage = event.get("usageMetadata") or {}
    chunk = usage_chunk(usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))
    if chunk:
        chunks.append(chunk)
    return chunks
