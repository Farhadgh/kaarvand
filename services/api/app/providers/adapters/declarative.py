"""Declarative adapter: a new, unusual provider protocol needs JSON, not code."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from app.providers.adapters.chat_common import make_client
from app.providers.adapters.litellm_catalog import _get_json  # shared helper
from app.providers.adapters.litellm_endpoints import base_url, build_headers, build_query_params
from app.providers.base import Chunk, ConnectionResult, RemoteModel, RemotePrice
from app.providers.credentials import decrypt_api_key, scrub
from app.providers.jsonpath import fill, resolve, resolve_list


class DeclarativeAdapter:
    kind = "declarative"

    async def list_models(self, provider: Any) -> list[RemoteModel]:
        spec = provider.chat_spec or {}
        url_template = spec.get("models_url") or provider.models_url
        if not url_template:
            return []
        url = fill(url_template, {"base_url": base_url(provider)})
        if not isinstance(url, str):
            return []
        payload = await _get_json(provider, url, timeout=30.0)

        mapping = spec.get("models_map") or {}
        ids = resolve_list(payload, mapping.get("id", "$.data[*].id"))
        contexts = resolve_list(payload, mapping["context"]) if mapping.get("context") else []
        names = resolve_list(payload, mapping["name"]) if mapping.get("name") else []

        out: list[RemoteModel] = []
        for index, model_id in enumerate(ids):
            raw_context = contexts[index] if index < len(contexts) else None
            context = int(raw_context) if str(raw_context or "").isdigit() else None
            name = names[index] if index < len(names) else None
            out.append(
                RemoteModel(
                    external_id=str(model_id),
                    display_name=str(name) if name else None,
                    context_window=context,
                )
            )
        return out

    async def fetch_prices(self, provider: Any) -> list[RemotePrice]:
        return []  # prices entered in the panel (manual override wins anyway)

    async def test(self, provider: Any, *, timeout: float = 20.0) -> ConnectionResult:
        started = time.perf_counter()
        try:
            models = await self.list_models(provider)
        except Exception as exc:  # noqa: BLE001
            return ConnectionResult(
                ok=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code="provider.connection_failed",
                detail=scrub(provider, str(exc)),
            )
        return ConnectionResult(
            ok=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
            models_seen=len(models),
        )

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
        spec = provider.chat_spec or {}
        chat = spec.get("chat") or {}
        if not chat.get("url"):
            yield Chunk(type="error", error_code="provider.missing_chat_spec")
            return

        api_key = decrypt_api_key(provider)
        variables: dict[str, Any] = {
            "base_url": base_url(provider),
            "api_key": api_key or "",
            "model": model,
            "messages": messages,
            "messages_flat": "\n".join(str(m.get("content", "")) for m in messages),
            "stream": False,
            "tools": tools or [],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = fill(chat.get("url"), variables)
        body = fill(chat.get("body") or {}, variables)
        headers = build_headers(provider, api_key)
        headers.update(fill(chat.get("headers") or {}, variables))

        try:
            async with make_client(provider, timeout=60.0) as client:
                response = await client.request(
                    str(chat.get("method") or "POST"),
                    str(url),
                    headers=headers,
                    params=build_query_params(provider, api_key),
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            yield Chunk(
                type="error",
                error_code="provider.call_failed",
                detail=scrub(provider, str(exc)),
            )
            return

        mapping = provider.response_map or {}
        text = resolve(payload, mapping.get("text", "$.choices[0].message.content"))
        if text:
            yield Chunk(type="text", text=str(text))

        usage_in = resolve(payload, mapping["usage_in"]) if mapping.get("usage_in") else None
        usage_out = resolve(payload, mapping["usage_out"]) if mapping.get("usage_out") else None
        if usage_in is not None or usage_out is not None:
            yield Chunk(
                type="usage",
                tokens_in=int(usage_in or 0),
                tokens_out=int(usage_out or 0),
            )
        yield Chunk(type="done")
