"""Adapter registry: provider kind -> adapter instance."""

from __future__ import annotations

from app.core.errors import AppError
from app.providers.adapters.anthropic_chat import AnthropicAdapter
from app.providers.adapters.declarative import DeclarativeAdapter
from app.providers.adapters.gemini_chat import GeminiAdapter
from app.providers.adapters.openai_chat import OPENAI_KINDS, OpenAICompatibleAdapter
from app.providers.base import ProviderAdapter

NATIVE_KINDS = OPENAI_KINDS | {"anthropic", "gemini"}


def get_adapter(kind: str) -> ProviderAdapter:
    if kind in OPENAI_KINDS:
        return OpenAICompatibleAdapter(kind)
    if kind == "anthropic":
        return AnthropicAdapter()
    if kind == "gemini":
        return GeminiAdapter()
    if kind == "declarative":
        return DeclarativeAdapter()
    raise AppError(
        code="provider.unknown_kind",
        status_code=400,
        params={"kind": kind, "supported": known_kinds()},
    )


def known_kinds() -> list[str]:
    return sorted({*NATIVE_KINDS, "declarative"})
