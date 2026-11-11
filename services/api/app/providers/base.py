"""Provider adapter contract.

An adapter talks to one *kind* of provider (openai, anthropic, declarative ...).
Everything tenant specific (base url, key, headers) comes from the database row,
so adding a provider never requires code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class RemoteModel:
    external_id: str
    display_name: str | None = None
    context_window: int | None = None
    max_output: int | None = None
    modalities: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RemotePrice:
    external_id: str
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    cached_input_price: Decimal | None = None
    image_price: Decimal | None = None
    currency: str = "USD"
    source: str = "provider"


@dataclass(slots=True)
class ConnectionResult:
    ok: bool
    latency_ms: int
    error_code: str | None = None
    detail: str | None = None
    models_seen: int | None = None


@dataclass(slots=True)
class Chunk:
    """Normalised stream event, independent of the upstream protocol."""

    type: str  # text | tool_call | usage | error | done
    text: str | None = None
    tool_call: dict[str, Any] | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    error_code: str | None = None
    detail: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    kind: str

    async def list_models(self, provider: Any) -> list[RemoteModel]: ...

    async def fetch_prices(self, provider: Any) -> list[RemotePrice]: ...

    async def test(self, provider: Any, *, timeout: float = 20.0) -> ConnectionResult: ...

    def stream_chat(
        self,
        provider: Any,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[Chunk]: ...
