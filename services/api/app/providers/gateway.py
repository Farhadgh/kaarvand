"""Chat gateway: unified streaming with automatic provider fallback."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Model, Provider
from app.providers.base import Chunk
from app.providers.registry import get_adapter


async def resolve_fallback(db: AsyncSession, model: Model) -> tuple[Provider, Model] | None:
    """Same model on another provider, else same family with same capabilities."""
    same_model = (
        await db.execute(
            select(Model, Provider)
            .join(Provider, Provider.id == Model.provider_id)
            .where(
                Model.id != model.id,
                Model.external_id == model.external_id,
                Model.is_enabled.is_(True),
                Provider.is_enabled.is_(True),
            )
            .order_by(Provider.priority.asc())
            .limit(1)
        )
    ).first()
    if same_model is not None:
        return same_model[1], same_model[0]

    if model.family:
        same_family = (
            await db.execute(
                select(Model, Provider)
                .join(Provider, Provider.id == Model.provider_id)
                .where(
                    Model.id != model.id,
                    Model.family == model.family,
                    Model.supports_tools == model.supports_tools,
                    Model.is_enabled.is_(True),
                    Provider.is_enabled.is_(True),
                )
                .order_by(Provider.priority.asc())
                .limit(1)
            )
        ).first()
        if same_family is not None:
            return same_family[1], same_family[0]
    return None


async def _stream_with(
    provider: Provider,
    model: Model,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float | None,
    max_tokens: int | None,
) -> AsyncIterator[Chunk]:
    adapter = get_adapter(provider.kind)
    async for chunk in adapter.stream_chat(
        provider,
        model=model.external_id,
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        yield chunk


async def stream_model(
    db: AsyncSession,
    *,
    model: Model,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    use_fallback: bool = True,
) -> AsyncIterator[Chunk]:
    provider = await db.get(Provider, model.provider_id)
    if provider is None:
        yield Chunk(type="error", error_code="provider.not_found")
        return

    failed = False
    async for chunk in _stream_with(
        provider,
        model,
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        if chunk.type == "error" and not failed and use_fallback:
            failed = True
            fallback = await resolve_fallback(db, model)
            if fallback is None:
                yield chunk
                return
            fb_provider, fb_model = fallback
            yield Chunk(
                type="notice",
                error_code=chunk.error_code,
                detail=f"fallback:{fb_provider.slug}/{fb_model.external_id}",
            )
            async for fb_chunk in _stream_with(
                fb_provider,
                fb_model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield fb_chunk
            return
        yield chunk
