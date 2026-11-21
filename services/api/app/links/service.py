"""Account link domain logic: ownership, provisioning and device commands.

A browser link is only a *permission*: the secrets (cookies) live in the desktop
app's Chromium profile. What the server keeps is the provider, who authorized it
and which device holds the session. Everything else - approvals, rate limits,
audit, cost - rides on the ordinary tool pipeline, because provisioning turns a
recipe into a ``kind='connector'`` tool.

The one wire rule: the server asks the device with ``type='link.command'`` and
the device answers ``type='link.result'`` carrying the same ``call_id``.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.hub import DeviceSession, hub
from app.core.deps import owns_or_admin
from app.core.errors import AppError, NotFoundError
from app.db.models import AccountLink, Device, LinkAsset, Tool, User
from app.links.providers import LinkProvider, get_provider
from app.tools.actions import validate_actions

LINK_TIMEOUT = 90.0


def tool_prefix(link: AccountLink) -> str:
    """Tools are named ``<provider>.<link8>.<tool>`` so a link owns only its own."""
    return f"{link.provider}.{str(link.id)[:8]}"


def tool_slug(link: AccountLink, name: str) -> str:
    return f"{tool_prefix(link)}.{name}"[:120]


async def get_link(db: AsyncSession, user: User, link_id: uuid.UUID) -> AccountLink:
    link = (
        await db.execute(
            select(AccountLink).where(
                AccountLink.id == link_id, AccountLink.org_id == user.org_id
            )
        )
    ).scalar_one_or_none()
    if link is None or not owns_or_admin(user, link.user_id):
        raise NotFoundError(code="link.not_found")
    return link


def _unknown_provider(slug: str) -> AppError:
    return AppError(code="link.unknown_provider", status_code=422, params={"provider": slug})


async def require_provider(slug: str) -> LinkProvider:
    provider = get_provider(slug)
    if provider is None:
        raise _unknown_provider(slug)
    if not provider.available:
        raise AppError(
            code="link.provider_soon",
            status_code=422,
            params={"provider": provider.slug},
        )
    return provider


async def pick_device(
    db: AsyncSession, user: User, device_id: uuid.UUID | None = None
) -> tuple[Device, DeviceSession]:
    """The device that will run the browser recipe: the caller's own by default."""
    online = {session.device_id: session for session in hub.online_devices(user.org_id)}
    if not online:
        raise AppError(code="link.device_offline", status_code=409, params={"device_id": None})

    devices = {
        row.id: row
        for row in (
            await db.execute(select(Device).where(Device.id.in_(list(online.keys()))))
        )
        .scalars()
        .all()
    }

    if device_id is not None:
        device = devices.get(device_id)
        if device is None or not owns_or_admin(user, device.owner_user_id):
            raise NotFoundError(code="device.not_found")
        return device, online[device_id]

    mine = [
        devices[session_id]
        for session_id in online
        if session_id in devices and owns_or_admin(user, devices[session_id].owner_user_id)
    ]
    if not mine:
        raise AppError(code="link.device_offline", status_code=409, params={"device_id": None})
    device = sorted(mine, key=lambda row: row.created_at)[0]
    return device, online[device.id]


async def send_command(
    db: AsyncSession,
    user: User,
    link: AccountLink,
    action: str,
    **extra: Any,
) -> dict[str, Any]:
    """Ask the device to do something for this link and wait for its answer."""
    device, session = await pick_device(db, user, link.device_id)
    reply = await hub.call(
        session=session,
        message={
            "type": "link.command",
            "action": action,
            "link_id": str(link.id),
            "provider": link.provider,
            **extra,
        },
        timeout=LINK_TIMEOUT,
    )
    # remember where the session actually lives
    if link.device_id != device.id:
        link.device_id = device.id
    if not reply.get("ok", False):
        raise AppError(
            code="link.device_error",
            status_code=502,
            params={
                "action": action,
                "detail": str(reply.get("error") or "")[:300],
                "step": reply.get("step"),
            },
        )
    return reply


async def provision_tools(db: AsyncSession, link: AccountLink) -> list[Tool]:
    """Turn the provider recipe into ordinary connector tools (idempotent)."""
    provider = get_provider(link.provider)
    if provider is None:
        raise _unknown_provider(link.provider)

    prefix = tool_prefix(link)
    existing = {
        row.slug: row
        for row in (
            await db.execute(select(Tool).where(Tool.slug.like(f"{prefix}.%")))
        )
        .scalars()
        .all()
    }

    label = link.display_name or provider.title_fa
    tools: list[Tool] = []
    for recipe in provider.tools:
        slug = tool_slug(link, recipe.name)
        steps = validate_actions([dict(step) for step in recipe.steps])
        config = {
            "link_id": str(link.id),
            "provider": link.provider,
            "device_id": str(link.device_id) if link.device_id else None,
            "transport": link.transport,
            "rate_limit_per_hour": link.rate_limit_per_hour,
        }
        tool = existing.pop(slug, None)
        if tool is None:
            tool = Tool(slug=slug, org_id=link.org_id)
            db.add(tool)
        tool.name_fa = f"{recipe.title_fa} — {label}"[:200]
        tool.description_fa = recipe.description_fa
        tool.kind = "connector"
        tool.input_schema = dict(recipe.input_schema)
        tool.output_schema = {}
        tool.config = config
        tool.actions = steps
        tool.risk_level = recipe.risk_level
        tool.approval_policy = recipe.approval_policy
        tool.category = "social"
        tool.is_enabled = True
        tool.created_by = link.user_id
        tools.append(tool)

    # a provider that dropped a tool must not leave a stale one behind
    for stale in existing.values():
        await db.delete(stale)

    await db.flush()
    return tools


async def drop_tools(db: AsyncSession, link: AccountLink) -> None:
    await db.execute(delete(Tool).where(Tool.slug.like(f"{tool_prefix(link)}.%")))
    await db.flush()


async def upsert_site(db: AsyncSession, link: AccountLink, provider: LinkProvider) -> None:
    """One asset row per link: the site the session belongs to."""
    row = (
        await db.execute(
            select(LinkAsset).where(
                LinkAsset.link_id == link.id,
                LinkAsset.kind == "site",
                LinkAsset.external_id == provider.slug,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = LinkAsset(
            org_id=link.org_id,
            link_id=link.id,
            kind="site",
            external_id=provider.slug,
        )
        db.add(row)
    row.name = provider.title_fa
    row.meta = {"site_url": provider.site_url, "auth_kind": provider.auth_kind}
    row.is_enabled = True
    await db.flush()


def _hint(provider: LinkProvider, reply: dict[str, Any]) -> str | None:
    if reply.get("logged_in"):
        return None
    return provider.login_hint_fa


async def probe(db: AsyncSession, user: User, link: AccountLink) -> dict[str, Any]:
    """Is the browser profile still logged in? Also (re)provisions the tools."""
    provider = get_provider(link.provider)
    if provider is None:
        raise _unknown_provider(link.provider)

    reply = await send_command(
        db,
        user,
        link,
        "probe",
        site_url=provider.site_url,
        login_check=provider.login_check,
    )

    logged_in = bool(reply.get("logged_in"))
    link.status = "active" if logged_in else "pending"
    link.last_error = None if logged_in else "link.login_required"
    link.last_seen_at = datetime.now(UTC) if logged_in else link.last_seen_at
    if logged_in:
        link.display_name = str(reply.get("display_name") or "")[:200] or link.display_name
        link.avatar_url = reply.get("avatar_url") or link.avatar_url
        link.external_account_id = (
            str(reply.get("external_account_id") or "")[:160] or link.external_account_id
        )
        await upsert_site(db, link, provider)
        tools = await provision_tools(db, link)
        slugs = [tool.slug for tool in tools]
    else:
        slugs = []
    await db.flush()

    return {
        "logged_in": logged_in,
        "status": link.status,
        "display_name": link.display_name,
        "external_account_id": link.external_account_id,
        "hint_fa": _hint(provider, reply),
        "tools": slugs,
        "screenshot": reply.get("screenshot"),
        "detail": reply.get("detail"),
    }



async def open_login(db: AsyncSession, user: User, link: AccountLink) -> dict[str, Any]:
    """Show the site window on the device so the owner can log in once."""
    provider = get_provider(link.provider)
    if provider is None:
        raise _unknown_provider(link.provider)
    reply = await send_command(db, user, link, "open", site_url=provider.site_url)
    link.last_error = None
    await db.flush()
    return {"ok": True, "window": reply.get("window") or provider.title_fa}


async def stop(db: AsyncSession, user: User, link: AccountLink) -> AccountLink:
    """Emergency switch: the bridge refuses further commands until re-probed."""
    await send_command(db, user, link, "stop")
    link.status = "paused"
    await db.flush()
    return link


async def disconnect(db: AsyncSession, user: User, link: AccountLink) -> None:
    """Wipe the browser profile on the device, then remove the link and its tools."""
    provider = get_provider(link.provider)
    if link.device_id is not None and provider is not None:
        # an offline laptop must not block the customer from disconnecting
        with contextlib.suppress(AppError):
            await send_command(db, user, link, "wipe")
    await drop_tools(db, link)
    await db.execute(delete(LinkAsset).where(LinkAsset.link_id == link.id))
    await db.delete(link)
    await db.flush()
