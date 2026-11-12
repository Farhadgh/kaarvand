"""Native OpenAI-compatible adapter (9 provider kinds, zero SDK)."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.errors import AppError
from app.providers.adapters.audio_pcm import to_wav
from app.providers.adapters.chat_common import (
    error_from_exception,
    http_code,
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
AUDIO_KINDS = {"openai", "openai_compatible", "groq", "azure_openai", "together", "openrouter"}

# OpenRouter's transcription endpoint wants JSON + base64 audio (not multipart)
OPENROUTER_AUDIO_FORMATS = {"wav", "mp3", "flac", "m4a", "ogg", "webm", "aac"}

AUDIO_MIME = {
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}

logger = logging.getLogger(__name__)

#: ``only supports response_format="pcm"`` -> the format the provider wants.
_ALLOWED_FORMAT_RE = re.compile(r"response_format\s*=?\s*\\?\"?([a-z0-9]{3,5})", re.IGNORECASE)


def _http_code(status_code: int) -> str:
    """Upstream status -> translatable code (see ``chat_common.http_code``)."""
    return http_code(status_code)



def _provider_error(
    provider: Any,
    status_code: int,
    body: str,
    *,
    model: str,
    endpoint: str,
) -> AppError:
    """Log (scrubbed) upstream rejections so they are debuggable after the fact."""
    from app.providers.credentials import scrub

    detail = scrub(provider, body[:400])
    code = _http_code(status_code)
    if status_code < 500:
        logger.warning(
            "provider %s rejected %s on %s with %s: %s",
            getattr(provider, "kind", "?"),
            model,
            endpoint,
            status_code,
            detail,
        )
    else:
        logger.error(
            "provider %s failed on %s for %s with %s: %s",
            getattr(provider, "kind", "?"),
            endpoint,
            model,
            status_code,
            detail,
        )
    return AppError(code=code, status_code=502, params={"detail": detail})


def _wanted_format(body: str) -> str | None:
    """Extract the single format a picky provider accepts (if it says so)."""
    if "response_format" not in body:
        return None
    match = _ALLOWED_FORMAT_RE.search(body)
    return match.group(1).lower() if match else None


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

    @staticmethod
    def _audio_format(filename: str, mime: str | None) -> str:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix in OPENROUTER_AUDIO_FORMATS:
            return suffix
        by_mime = {
            "audio/wav": "wav",
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/flac": "flac",
            "audio/mp4": "m4a",
            "audio/ogg": "ogg",
            "audio/webm": "webm",
            "audio/aac": "aac",
        }
        return by_mime.get((mime or "").split(";")[0].strip().lower(), "webm")

    async def _transcribe_openrouter(
        self,
        provider: Any,
        *,
        model: str,
        content: bytes,
        filename: str,
        mime: str | None,
        language: str | None,
        prompt: str | None,
    ) -> dict[str, Any]:
        """OpenRouter wants ``{"model", "input_audio": {"data", "format"}}`` (base64)."""
        import base64

        from app.providers.credentials import decrypt_api_key, scrub

        base = base_url(provider)
        if not base:
            raise AppError(code="provider.missing_base_url", status_code=422)

        api_key = decrypt_api_key(provider)
        body: dict[str, Any] = {
            "model": model,
            "input_audio": {
                "data": base64.b64encode(content).decode("ascii"),
                "format": self._audio_format(filename, mime),
            },
        }
        if language:
            body["language"] = language
        if prompt:
            body["prompt"] = prompt[:1000]

        try:
            async with make_client(provider, timeout=180.0) as client:
                response = await client.post(
                    self._audio_url(provider, "transcriptions", model),
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
            raise _provider_error(
                provider,
                response.status_code,
                response.text,
                model=model,
                endpoint="audio/transcriptions",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(code="audio.invalid_response", status_code=502) from exc
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        seconds = usage.get("seconds") or usage.get("duration") or payload.get("duration")
        return {
            "text": str(payload.get("text") or ""),
            "language": payload.get("language"),
            "duration": float(seconds or 0.0),
        }

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
        """Speech-to-text via ``POST /audio/transcriptions``."""
        from app.providers.credentials import decrypt_api_key, scrub

        if self.kind not in AUDIO_KINDS:
            raise AppError(
                code="audio.unsupported_provider",
                status_code=422,
                params={"kind": self.kind, "supported": sorted(AUDIO_KINDS)},
            )
        if self.kind == "openrouter":
            return await self._transcribe_openrouter(
                provider,
                model=model,
                content=content,
                filename=filename,
                mime=mime,
                language=language,
                prompt=prompt,
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
            raise _provider_error(
                provider,
                response.status_code,
                response.text,
                model=model,
                endpoint="audio/transcriptions",
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

    async def _post_speech(
        self,
        provider: Any,
        api_key: str | None,
        body: dict[str, Any],
    ) -> httpx.Response:
        from app.providers.credentials import scrub

        try:
            async with make_client(provider, timeout=180.0) as client:
                return await client.post(
                    self._audio_url(provider, "speech", str(body["model"])),
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
        """Text-to-speech via ``POST /audio/speech`` -> (audio bytes, mime).

        Some models (``google/gemini-*-tts``, ``heygen/*`` …) accept *only* one
        ``response_format`` and answer ``400`` otherwise. Instead of failing we
        read the format the provider asks for from its error message, retry once,
        and wrap raw PCM into WAV so the browser can play it.
        """
        from app.providers.credentials import decrypt_api_key

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

        response = await self._post_speech(provider, api_key, body)
        if response.status_code == 400:
            wanted = _wanted_format(response.text)
            if wanted and wanted != body["response_format"]:
                logger.info(
                    "model %s only accepts response_format=%s (asked %s); retrying",
                    model,
                    wanted,
                    body["response_format"],
                )
                body["response_format"] = wanted
                response = await self._post_speech(provider, api_key, body)

        if response.status_code >= 400:
            raise _provider_error(
                provider,
                response.status_code,
                response.text,
                model=model,
                endpoint="audio/speech",
            )

        content_type = response.headers.get("content-type", "")
        if content_type.split(";")[0].strip().lower() == "audio/pcm":
            return to_wav(response.content, content_type), "audio/wav"
        return response.content, AUDIO_MIME.get(str(body["response_format"]), "audio/mpeg")

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
