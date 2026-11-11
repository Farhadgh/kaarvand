"""Endpoint knowledge for OpenAI-ish providers.

All endpoint knowledge lives here (not in business logic) and every endpoint can
be overridden per provider by ``models_url`` / ``prices_url`` in the database.
"""

from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
from typing import Any

from app.providers.base import RemoteModel

LITELLM_PREFIX = {
    "openai": "openai",
    "openai_compatible": "openai",
    "openrouter": "openrouter",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "azure_openai": "azure",
    "groq": "groq",
    "deepseek": "deepseek",
    "mistral": "mistral",
    "together": "together_ai",
    "ollama": "ollama",
}

DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "ollama": "http://127.0.0.1:11434",
}

DEFAULT_MODELS_SUFFIX = {"ollama": "/api/tags", "gemini": "/models"}


def base_url(provider: Any) -> str:
    configured = getattr(provider, "base_url", None) or DEFAULT_BASE.get(provider.kind, "")
    return configured.rstrip("/")


def chat_model_string(provider: Any, external_id: str) -> str:
    """Build the canonical ``prefix/model`` reference used by the price table."""
    prefix = LITELLM_PREFIX.get(provider.kind, "openai")
    if provider.kind == "openrouter" and not external_id.startswith("openrouter/"):
        return f"openrouter/{external_id}"
    if external_id.startswith(f"{prefix}/"):
        return external_id
    return f"{prefix}/{external_id}"


def build_headers(provider: Any, api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        if provider.kind == "anthropic":
            headers["x-api-key"] = api_key
            headers.setdefault("anthropic-version", "2023-06-01")
        elif provider.auth_type == "api_key_header":
            headers["api-key"] = api_key
        elif provider.auth_type == "basic":
            headers["Authorization"] = f"Basic {base64.b64encode(api_key.encode()).decode()}"
        elif provider.kind != "gemini" and provider.auth_type != "query":
            headers["Authorization"] = f"Bearer {api_key}"

    for key, value in (getattr(provider, "extra_headers", None) or {}).items():
        headers[str(key)] = str(value)
    return headers


def build_query_params(provider: Any, api_key: str | None) -> dict[str, str]:
    if api_key and provider.kind == "gemini":
        return {"key": api_key}
    if api_key and provider.auth_type == "query":
        return {"api_key": api_key}
    return {}


def models_endpoint(provider: Any) -> str | None:
    explicit = getattr(provider, "models_url", None)
    if explicit:
        return explicit
    base = base_url(provider)
    if not base:
        return None
    return f"{base}{DEFAULT_MODELS_SUFFIX.get(provider.kind, '/models')}"


def parse_models(provider: Any, payload: dict[str, Any]) -> list[RemoteModel]:
    if provider.kind == "gemini":
        return _parse_gemini(payload)
    if provider.kind == "ollama":
        return _parse_ollama(payload)
    return _parse_openai_style(payload)


def _parse_openai_style(payload: dict[str, Any]) -> list[RemoteModel]:
    out: list[RemoteModel] = []
    for item in payload.get("data") or []:
        model_id = item.get("id") or item.get("model")
        if not model_id:
            continue
        architecture = item.get("architecture") or {}
        out.append(
            RemoteModel(
                external_id=model_id,
                display_name=item.get("display_name") or item.get("name"),
                context_window=item.get("context_length") or item.get("context_window"),
                max_output=item.get("max_completion_tokens"),
                modalities=list(architecture.get("input_modalities") or []),
                meta={
                    key: value
                    for key, value in item.items()
                    if key in {"owned_by", "created", "pricing", "architecture"}
                },
            )
        )
    return out


def _parse_gemini(payload: dict[str, Any]) -> list[RemoteModel]:
    out: list[RemoteModel] = []
    for item in payload.get("models") or []:
        name = item.get("name") or ""
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        out.append(
            RemoteModel(
                external_id=name.replace("models/", "", 1),
                display_name=item.get("displayName"),
                context_window=item.get("inputTokenLimit"),
                max_output=item.get("outputTokenLimit"),
            )
        )
    return out


def _parse_ollama(payload: dict[str, Any]) -> list[RemoteModel]:
    return [
        RemoteModel(external_id=item["name"], meta={"size": item.get("size")})
        for item in payload.get("models") or []
        if item.get("name")
    ]


def to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
