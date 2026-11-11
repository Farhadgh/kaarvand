"""Native Anthropic (Messages API) adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.adapters.chat_common import (
    anthropic_messages,
    anthropic_tools,
    error_from_exception,
    http_error,
    make_client,
    sse_events,
    usage_chunk,
)
from app.providers.adapters.litellm_catalog import fetch_prices, list_models, test_connection
from app.providers.adapters.litellm_endpoints import base_url, build_headers
from app.providers.base import Chunk, ConnectionResult, RemoteModel, RemotePrice
from app.providers.credentials import decrypt_api_key

DEFAULT_MAX_TOKENS = 1024


class AnthropicAdapter:
    kind = "anthropic"

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
        system, converted = anthropic_messages(messages)
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens or DEFAULT_MAX_TOKENS),
            "messages": converted,
            "stream": True,
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = float(temperature)
        if tools:
            converted_tools = anthropic_tools(tools)
            if converted_tools:
                body["tools"] = converted_tools

        timeout = httpx.Timeout(180.0, connect=20.0)
        try:
            async with make_client(provider, timeout=timeout) as client:
                request = client.stream(
                    "POST",
                    f"{base}/messages",
                    headers=build_headers(provider, api_key),
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


def _parse_event(event: dict[str, Any]) -> list[Chunk]:
    kind = event.get("type")
    chunks: list[Chunk] = []

    if kind == "content_block_delta":
        delta = event.get("delta") or {}
        if delta.get("type") == "text_delta" and delta.get("text"):
            chunks.append(Chunk(type="text", text=str(delta["text"])))
        elif delta.get("type") == "input_json_delta" and delta.get("partial_json"):
            chunks.append(
                Chunk(
                    type="tool_call",
                    tool_call={"arguments": delta["partial_json"]},
                )
            )
    elif kind == "content_block_start":
        block = event.get("content_block") or {}
        if block.get("type") == "tool_use":
            chunks.append(
                Chunk(
                    type="tool_call",
                    tool_call={"id": block.get("id"), "name": block.get("name")},
                )
            )
    elif kind == "message_start":
        usage = (event.get("message") or {}).get("usage") or {}
        chunk = usage_chunk(usage.get("input_tokens"), None)
        if chunk:
            chunks.append(chunk)
    elif kind == "message_delta":
        usage = event.get("usage") or {}
        chunk = usage_chunk(None, usage.get("output_tokens"))
        if chunk:
            chunks.append(chunk)
    elif kind == "error":
        error = event.get("error") or {}
        chunks.append(
            Chunk(
                type="error",
                error_code="provider.call_failed",
                detail=str(error.get("message") or "unknown error")[:800],
            )
        )
    return chunks
