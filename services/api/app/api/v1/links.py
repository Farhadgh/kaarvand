"""Account links API: «حساب‌های من» - connect once, then act as the customer.

Every endpoint is per user: another customer's link is a 404, never a 403, so
the API never confirms that someone else's account exists. The heavy lifting
lives in ``app/links/service.py``; this module only shapes the responses.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.hub import hub
from app.core.deps import ADMIN_ROLE, get_current_user, get_db, require_member
from app.core.errors import AppError, NotFoundError
from app.db.models import AccountLink, LinkAsset, Tool, User
from app.links import service
from app.links.providers import LinkProvider, catalog, get_provider
from app.schemas.links import (
    LinkAssetOut,
    LinkCreate,
    LinkOpenOut,
    LinkOut,
    LinkProbeOut,
    LinkProviderOut,
    LinkSyncOut,
    LinkToolOut,
)

router = APIRouter(tags=["links"])
editor = require_member


def _provider_out(provider: LinkProvider) -> LinkProviderOut:
    return LinkProviderOut(
        slug=provider.slug,
        title_fa=provider.title_fa,
        auth_kind=provider.auth_kind,
        site_url=provider.site_url,
        login_hint_fa=provider.login_hint_fa,
        notes_fa=provider.notes_fa,
        rate_limit_per_hour=provider.rate_limit_per_hour,
        available=provider.available,
        tools=[
            LinkToolOut(
                name=tool.name,
                title_fa=tool.title_fa,
                description_fa=tool.description_fa,
                input_schema=tool.input_schema,
            )
            for tool in provider.tools
        ],
    )


def _link_out(link: AccountLink, *, tools: list[str] | None = None) -> LinkOut:
    out = LinkOut.model_validate(link)
    provider = get_provider(link.provider)
    out.provider_title_fa = provider.title_fa if provider else link.provider
    out.device_online = link.device_id is not None and hub.get(link.device_id) is not None
    out.tool_slugs = tools or []
    return out


async def _tool_map(db: AsyncSession, links: list[AccountLink]) -> dict[str, list[str]]:
    if not links:
        return {}
    link_ids = [str(link.id) for link in links]
    rows = (
        await db.execute(
            select(Tool.config["link_id"].astext, Tool.slug)
            .where(Tool.config["link_id"].astext.in_(link_ids))
            .order_by(Tool.slug)
        )
    ).all()
    result: dict[str, list[str]] = {}
    for link_id, slug in rows:
        result.setdefault(str(link_id), []).append(slug)
    return result


@router.get("/links/providers", response_model=list[LinkProviderOut])
async def list_link_providers(_: User = Depends(get_current_user)) -> list[LinkProviderOut]:
    """The cards to render: available providers first, then «به‌زودی» ones."""
    return [_provider_out(provider) for provider in catalog()]


@router.get("/links", response_model=list[LinkOut])
async def list_links(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LinkOut]:
    stmt = select(AccountLink).where(AccountLink.org_id == user.org_id)
    if user.role != ADMIN_ROLE:
        stmt = stmt.where(AccountLink.user_id == user.id)
    links = (
        (await db.execute(stmt.order_by(AccountLink.created_at.desc()))).scalars().all()
    )
    tools = await _tool_map(db, list(links))
    return [_link_out(link, tools=tools.get(str(link.id), [])) for link in links]


@router.post("/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(
    payload: LinkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> LinkOut:
    """Create the pending link and, when the device is online, open the login window."""
    provider = await service.require_provider(payload.provider)

    existing = (
        await db.execute(
            select(AccountLink).where(
                AccountLink.user_id == user.id,
                AccountLink.provider == provider.slug,
                AccountLink.status != "revoked",
            )
        )
    ).scalars().first()
    if existing is not None:
        raise AppError(
            code="link.already_exists",
            status_code=409,
            params={"link_id": str(existing.id), "provider": provider.slug},
        )

    link = AccountLink(
        org_id=user.org_id,
        user_id=user.id,
        provider=provider.slug,
        auth_kind=provider.auth_kind,
        transport="device" if provider.auth_kind == "browser" else "server",
        status="pending",
        rate_limit_per_hour=provider.rate_limit_per_hour,
        device_id=payload.device_id,
    )
    db.add(link)
    await db.flush()

    opened = False
    try:
        await service.open_login(db, user, link)
        opened = True
    except (AppError, NotFoundError):
        # no device yet: the card still exists and says «دستگاه آنلاین نیست»
        pass

    out = _link_out(link)
    out.login_opened = opened
    return out


@router.get("/links/{link_id}", response_model=LinkOut)
async def read_link(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LinkOut:
    link = await service.get_link(db, user, link_id)
    tools = await _tool_map(db, [link])
    return _link_out(link, tools=tools.get(str(link.id), []))


@router.post("/links/{link_id}/open", response_model=LinkOpenOut)
async def open_link_login(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> LinkOpenOut:
    link = await service.get_link(db, user, link_id)
    result = await service.open_login(db, user, link)
    return LinkOpenOut(ok=True, window=str(result.get("window") or ""))


@router.post("/links/{link_id}/probe", response_model=LinkProbeOut)
async def probe_link(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> LinkProbeOut:
    """Did the customer finish logging in? On success the tools are created."""
    link = await service.get_link(db, user, link_id)
    result = await service.probe(db, user, link)
    return LinkProbeOut(**result)


@router.post("/links/{link_id}/sync", response_model=LinkSyncOut)
async def sync_link_tools(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> LinkSyncOut:
    link = await service.get_link(db, user, link_id)
    if link.status != "active":
        raise AppError(code="link.not_active", status_code=409, params={"status": link.status})
    tools = await service.provision_tools(db, link)
    return LinkSyncOut(tools=[tool.slug for tool in tools], count=len(tools))


@router.post("/links/{link_id}/stop", response_model=LinkOut)
async def stop_link(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> LinkOut:
    link = await service.get_link(db, user, link_id)
    await service.stop(db, user, link)
    tools = await _tool_map(db, [link])
    return _link_out(link, tools=tools.get(str(link.id), []))


@router.get("/links/{link_id}/assets", response_model=list[LinkAssetOut])
async def list_link_assets(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LinkAssetOut]:
    link = await service.get_link(db, user, link_id)
    rows = (
        await db.execute(
            select(LinkAsset)
            .where(LinkAsset.link_id == link.id)
            .order_by(LinkAsset.kind, LinkAsset.name)
        )
    ).scalars().all()
    return [LinkAssetOut.model_validate(row) for row in rows]


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    """Disconnect: wipe the browser profile on the device, drop tools and the link."""
    link = await service.get_link(db, user, link_id)
    await service.disconnect(db, user, link)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _unused(*_: Any) -> None:  # pragma: no cover - keeps linters honest
    return None
