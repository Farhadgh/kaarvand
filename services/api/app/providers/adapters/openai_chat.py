"""Native OpenAI-compatible adapter (9 provider kinds, zero SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.errors import AppError
from app.providers.adapters.chat_common import (
    error_from_exception,
    http_error,
    make_client,
    openai_messages,
    sse_events,
    usage_chunk,
)
from app.providers.adapters.litellm_catalog import fetch_prices, list_models, test_connection
from app.providers.adapters.litellm_endpoints import (
    base_url,
    build_headers,
    build_query_params,
)
from app.providers.base import Chunk, ConnectionResult, RemoteModel, RemotePrice

OPENAI_KINDS = {
    "openai",
    "openai_compatible",
    "openrouter",
    "groq",
    "deepseek",
    "mistral",
    "together",
    "ollama",
    "azure_openai",
}

AZURE_API_VERSION = "2024-06-01"

# provider kinds that expose the OpenAI audio API (/audio/transcriptions, /audio/speech)
AUDIO_KINDS = {"openai", "openai_compatible", "groq", "azure_openai", "together"}

AUDIO_MIME = {
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


def _http_code(status_code: int) -> str:
    return "provider.auth_failed" if status_code in (401, 403) else f"provider.http_{status_code}"


class OpenAICompatibleAdapter:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    # --- catalog -----------------------------------------------------------
    async def list_models(self, provider: Any) -> list[RemoteModel]:
        return await list_models(provider)

    async def fetch_prices(self, provider: Any) -> list[RemotePrice]:
        return await fetch_prices(provider)

    async def test(self, provider: Any, *, timeout: float = 20.0) -> ConnectionResult:
        return await test_connection(provider, timeout=timeout)

    # --- chat --------------------------------------------------------------
    def _chat_url(self, provider: Any, model: str) -> str:
        base = base_url(provider)
        if self.kind == "azure_openai":
            return f"{base}/openai/deployments/{model}/chat/completions"
        if self.kind == "ollama":
            return f"{base}/v1/chat/completions"
        return f"{base}/chat/completions"

    def _params(self, provider: Any, api_key: str | None) -> dict[str, str]:
        params = build_query_params(provider, api_key)
        if self.kind == "azure_openai":
            params["api-version"] = (provider.meta or {}).get("api_version", AZURE_API_VERSION)
        return params

    def _headers(self, provider: Any, api_key: str | None) -> dict[str, str]:
        headers = build_headers(provider, api_key)
        if self.kind == "azure_openai" and api_key:
            headers["api-key"] = api_key
        if self.kind == "openrouter":
            headers.setdefault("HTTP-Referer", "https://kaarvand.ir")
            headers.setdefault("X-Title", "Kaarvand")
        return headers

    # --- audio (STT / TTS) --------------------------------------------------
    def _audio_url(self, provider: Any, path: str, model: str) -> str:
        base = base_url(provider)
        if self.kind == "azure_openai":
            return f"{base}/openai/deployments/{model}/audio/{path}"
        return f"{base}/audio/{path}"

    def _audio_headers(self, provider: Any, api_key: str | None) -> dict[str, str]:
        headers = dict(self._headers(provider, api_key))
        # multipart requests must carry the httpx generated boundary
        headers.pop("Content-Type", None)
        return headers

    async def transcribe(
        self,
        provider: Any,
        *,
        model: str,
        content: bytes,
        filename: str,
        mime: str | None = None,
        language: str | None = None,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Speech-to-text via ``POST /audio/transcriptions`` (multipart)."""
        from app.providers.credentials import decrypt_api_key, scrub

        if self.kind not in AUDIO_KINDS:
            raise AppError(
                code="audio.unsupported_provider",
                status_code=422,
                params={"kind": self.kind, "supported": sorted(AUDIO_KINDS)},
            )
        base = base_url(provider)
        if not base:
            raise AppError(code="provider.missing_base_url", status_code=422)

        api_key = decrypt_api_key(provider)
        data: dict[str, str] = {"model": model, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt[:1000]

        try:
            async with make_client(provider, timeout=180.0) as client:
                response = await client.post(
                    self._audio_url(provider, "transcriptions", model),
                    data=data,
                    files={"file": (filename, content, mime or "audio/webm")},
                    headers=self._audio_headers(provider, api_key),
                    params=self._params(provider, api_key),
                )
        except httpx.TimeoutException as exc:
            raise AppError(code="provider.timeout", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code="provider.call_failed",
                status_code=502,
                params={"detail": scrub(provider, str(exc))},
            ) from exc

        if response.status_code >= 400:
            raise AppError(
                code=_http_code(response.status_code),
                status_code=502,
                params={"detail": scrub(provider, response.text[:400])},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(code="audio.invalid_response", status_code=502) from exc
        text = str(payload.get("text") or "")
        seconds = payload.get("duration")
        if seconds is None and isinstance(payload.get("segments"), list):
            seconds = max(
                (float(segment.get("end") or 0) for segment in payload["segments"]), default=0.0
            )
        return {
            "text": text,
            "language": payload.get("language"),
            "duration": float(seconds or 0.0),
        }

    async def speech(
        self,
        provider: Any,
        *,
        model: str,
        text: str,
        voice: str = "alloy",
        fmt: str = "mp3",
        speed: float | None = None,
    ) -> tuple[bytes, str]:
        """Text-to-speech via ``POST /audio/speech`` -> (audio bytes, mime)."""
        from app.providers.credentials import decrypt_api_key, scrub

        if self.kind not in AUDIO_KINDS:
            raise AppError(
                code="audio.unsupported_provider",
                status_code=422,
                params={"kind": self.kind, "supported": sorted(AUDIO_KINDS)},
            )
        base = base_url(provider)
        if not base:
            raise AppError(code="provider.missing_base_url", status_code=422)

        api_key = decrypt_api_key(provider)
        body: dict[str, Any] = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": fmt,
        }
        if speed is not None:
            body["speed"] = float(speed)

        try:
            async with make_client(provider, timeout=180.0) as client:
                response = await client.post(
                    self._audio_url(provider, "speech", model),
                    json=body,
                    headers=self._headers(provider, api_key),
                    params=self._params(provider, api_key),
                )
        except httpx.TimeoutException as exc:
            raise AppError(code="provider.timeout", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code="provider.call_failed",
                status_code=502,
                params={"detail": scrub(provider, str(exc))},
            ) from exc

        if response.status_code >= 400:
            raise AppError(
                code=_http_code(response.status_code),
                status_code=502,
                params={"detail": scrub(provider, response.text[:400])},
            )
        return response.content, AUDIO_MIME.get(fmt, "audio/mpeg")

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
        from app.providers.credentials import decrypt_api_key

        base = base_url(provider)
        if not base:
            yield Chunk(type="error", error_code="provider.missing_base_url")
            return

        api_key = decrypt_api_key(provider)
        body: dict[str, Any] = {
            "model": model,
            "messages": openai_messages(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = float(temperature)
        if max_tokens:
            body["max_tokens"] = int(max_tokens)

        timeout = httpx.Timeout(180.0, connect=20.0)
        try:
            async with make_client(provider, timeout=timeout) as client:
                request = client.stream(
                    "POST",
                    self._chat_url(provider, model),
                    headers=self._headers(provider, api_key),
                    params=self._params(provider, api_key),
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
    chunks: list[Chunk] = []
    choices = event.get("choices") or []
    if choices:
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content:
            chunks.append(Chunk(type="text", text=str(content)))
        for call in delta.get("tool_calls") or []:
            function = call.get("function") or {}
            chunks.append(
                Chunk(
                    type="tool_call",
                    tool_call={
                        "index": call.get("index", 0),
                        "id": call.get("id"),
                        "name": function.get("name"),
                        "arguments": function.get("arguments"),
                    },
                )
            )
    usage = event.get("usage")
    if usage:
        chunk = usage_chunk(usage.get("prompt_tokens"), usage.get("completion_tokens"))
        if chunk:
            chunks.append(chunk)
    return chunks
