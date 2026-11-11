"""Inbound webhooks (public) + channel management (authenticated).

Public endpoints never return 5xx to a provider: a bad payload is acknowledged
and ignored, so Telegram/WhatsApp do not retry forever. Verification is
signature based (Telegram secret token, WhatsApp HMAC-SHA256 over the raw body).
"""

from __future__ import annotations

import asyncio
import hmac
import json
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import get_agent
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db, require_roles
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.db.models import InboundChannel, InboundEvent, Tool, User
from app.db.session import session_scope
from app.runtime.inbound import (
    IncomingMessage,
    accept_message,
    decrypt_channel_secret,
    decrypt_verify_token,
    encrypt_channel_secret,
    execute_plan,
    execute_plan_full,
    new_slug,
    parse_telegram,
    parse_whatsapp,
    telegram_secret_ok,
    whatsapp_signature_ok,
)
from app.schemas.inbound import (
    InboundAcceptedOut,
    InboundChannelCreate,
    InboundChannelOut,
    InboundChannelUpdate,
    InboundEventOut,
    InboundTestIn,
    InboundTestOut,
    WebhookRegisterOut,
)
from app.tools.secrets import decrypt_tool_secret

router = APIRouter(tags=["inbound"])
admin = require_roles("owner", "admin")
log = get_logger("openbot.inbound")

# keep a hard reference so the GC cannot cancel an in-flight run
_background: set[asyncio.Task[Any]] = set()


def _paths(channel: InboundChannel) -> tuple[str, str]:
    return (
        f"/v1/inbound/{channel.provider}/{channel.slug}",
        f"/v1/inbound/{channel.provider}/{channel.slug}",
    )


def _public_base(request: Request) -> tuple[str, bool]:
    """Absolute origin for webhook URLs: config first, request as fallback."""
    configured = (get_settings().public_base_url or "").strip().rstrip("/")
    if configured:
        return configured, True
    return str(request.base_url).rstrip("/"), False


def to_out(channel: InboundChannel, base: str = "") -> InboundChannelOut:
    out = InboundChannelOut.model_validate(channel)
    out.has_secret = bool(channel.verify_secret_enc)
    out.has_verify_token = bool(channel.verify_token_enc)
    webhook, verify = _paths(channel)
    out.webhook_path = webhook
    out.verify_path = verify
    out.webhook_url = f"{base}{webhook}" if base else webhook
    return out


async def _channel_by_slug(slug: str) -> InboundChannel:
    """Public lookup: the provider only knows the slug, not the tenant."""
    async with session_scope(bypass_rls=True) as db:
        channel = (
            await db.execute(select(InboundChannel).where(InboundChannel.slug == slug))
        ).scalar_one_or_none()
    if channel is None:
        raise NotFoundError(code="inbound.channel_not_found")
    return channel


def _schedule(plan: Any) -> None:
    task = asyncio.create_task(_run_plan(plan))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _run_plan(plan: Any) -> None:
    try:
        await execute_plan(plan)
    except Exception:  # noqa: BLE001 - a background failure must be logged, not raised
        log.exception("inbound.run_failed", run_id=str(plan.run_id))


async def _handle(channel: InboundChannel, messages: list[Any]) -> InboundAcceptedOut:
    if not messages:
        return InboundAcceptedOut(ok=True, status="ignored")
    run_ids: list[uuid.UUID] = []
    statuses: list[str] = []
    for message in messages:
        state, plan = await accept_message(channel, message)
        statuses.append(state)
        if plan is not None:
            run_ids.append(plan.run_id)
            _schedule(plan)
    return InboundAcceptedOut(
        ok=True,
        status=statuses[0] if statuses else "ignored",
        run_id=run_ids[0] if run_ids else None,
    )


# ------------------------------------------------------------------- webhooks
@router.post("/inbound/telegram/{slug}", response_model=InboundAcceptedOut)
async def telegram_webhook(slug: str, request: Request) -> InboundAcceptedOut:
    channel = await _channel_by_slug(slug)
    if channel.provider != "telegram":
        raise NotFoundError(code="inbound.channel_not_found")

    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not telegram_secret_ok(channel, header):
        raise AppError(code="inbound.invalid_signature", status_code=401)

    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise AppError(code="inbound.invalid_payload", status_code=400) from None
    if not isinstance(payload, dict):
        raise AppError(code="inbound.invalid_payload", status_code=400)

    return await _handle(channel, parse_telegram(payload))


@router.get("/inbound/whatsapp/{slug}")
async def whatsapp_verify(slug: str, request: Request) -> Response:
    channel = await _channel_by_slug(slug)
    if channel.provider != "whatsapp":
        raise NotFoundError(code="inbound.channel_not_found")

    params = request.query_params
    expected = decrypt_verify_token(channel)
    provided = str(params.get("hub.verify_token") or "")
    if not expected or not hmac.compare_digest(expected, provided):
        raise AppError(code="inbound.invalid_verify_token", status_code=403)
    if str(params.get("hub.mode") or "") != "subscribe":
        raise AppError(code="inbound.invalid_mode", status_code=400)
    return PlainTextResponse(str(params.get("hub.challenge") or ""))


@router.post("/inbound/whatsapp/{slug}", response_model=InboundAcceptedOut)
async def whatsapp_webhook(slug: str, request: Request) -> InboundAcceptedOut:
    channel = await _channel_by_slug(slug)
    if channel.provider != "whatsapp":
        raise NotFoundError(code="inbound.channel_not_found")

    raw = await request.body()
    if not whatsapp_signature_ok(channel, raw, request.headers.get("X-Hub-Signature-256")):
        raise AppError(code="inbound.invalid_signature", status_code=401)

    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise AppError(code="inbound.invalid_payload", status_code=400) from None
    if not isinstance(payload, dict):
        raise AppError(code="inbound.invalid_payload", status_code=400)

    return await _handle(channel, parse_whatsapp(payload))


# -------------------------------------------------------------------- channels
async def _get_channel(db: AsyncSession, user: User, channel_id: uuid.UUID) -> InboundChannel:
    channel = (
        await db.execute(
            select(InboundChannel).where(
                InboundChannel.id == channel_id, InboundChannel.org_id == user.org_id
            )
        )
    ).scalar_one_or_none()
    if channel is None:
        raise NotFoundError(code="inbound.channel_not_found")
    return channel


async def _validate_refs(
    db: AsyncSession,
    user: User,
    *,
    provider: str,
    agent_id: uuid.UUID,
    tool_id: uuid.UUID | None,
) -> None:
    await get_agent(db, user, agent_id)
    if tool_id is None:
        return
    tool = (
        await db.execute(
            select(Tool).where(
                Tool.id == tool_id,
                (Tool.org_id == user.org_id) | (Tool.org_id.is_(None)),
            )
        )
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError(code="tool.not_found")
    if tool.kind != "http":
        raise AppError(code="inbound.tool_not_http", status_code=422, params={"kind": tool.kind})
    app_slug = str((tool.config or {}).get("app_slug") or "")
    # a custom tool may have no app_slug at all; only reject a *mismatched* one
    if app_slug and not app_slug.startswith(provider):
        raise AppError(
            code="inbound.tool_provider_mismatch",
            status_code=422,
            params={"tool": app_slug, "provider": provider},
        )


@router.get("/channels", response_model=list[InboundChannelOut])
async def list_channels(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[InboundChannelOut]:
    rows = (
        (
            await db.execute(
                select(InboundChannel)
                .where(InboundChannel.org_id == user.org_id)
                .order_by(InboundChannel.created_at)
            )
        )
        .scalars()
        .all()
    )
    base, _ = _public_base(request)
    last: dict[uuid.UUID, InboundEvent] = {}
    if rows:
        events = (
            await db.execute(
                select(InboundEvent)
                .where(
                    InboundEvent.org_id == user.org_id,
                    InboundEvent.channel_id.in_([row.id for row in rows]),
                )
                .order_by(InboundEvent.channel_id, InboundEvent.created_at.desc())
                .distinct(InboundEvent.channel_id)
            )
        ).scalars()
        last = {event.channel_id: event for event in events}

    out: list[InboundChannelOut] = []
    for row in rows:
        item = to_out(row, base)
        event = last.get(row.id)
        if event is not None:
            item.last_event_status = event.status
            item.last_reply_status = event.reply_status
            item.last_error = event.error
        out.append(item)
    return out


@router.post("/channels", response_model=InboundChannelOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: InboundChannelCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin),
) -> InboundChannelOut:
    if not payload.verify_secret:
        raise AppError(
            code="inbound.secret_required", status_code=422, params={"provider": payload.provider}
        )
    if payload.provider == "whatsapp" and not payload.verify_token:
        raise AppError(
            code="inbound.verify_token_required", status_code=422, params={"provider": "whatsapp"}
        )
    await _validate_refs(
        db,
        user,
        provider=payload.provider,
        agent_id=payload.agent_id,
        tool_id=payload.tool_id,
    )

    channel = InboundChannel(
        org_id=user.org_id,
        slug=new_slug(payload.provider),
        name_fa=payload.name_fa,
        provider=payload.provider,
        agent_id=payload.agent_id,
        tool_id=payload.tool_id,
        reply_mode=payload.reply_mode,
        is_active=payload.is_active,
        created_by=user.id,
    )
    db.add(channel)
    await db.flush()
    channel.verify_secret_enc = encrypt_channel_secret(channel, payload.verify_secret)
    if payload.verify_token:
        channel.verify_token_enc = encrypt_channel_secret(channel, payload.verify_token)
    await db.flush()
    return to_out(channel, _public_base(request)[0])


@router.patch("/channels/{channel_id}", response_model=InboundChannelOut)
async def update_channel(
    channel_id: uuid.UUID,
    payload: InboundChannelUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin),
) -> InboundChannelOut:
    channel = await _get_channel(db, user, channel_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("agent_id") is not None or data.get("tool_id") is not None:
        await _validate_refs(
            db,
            user,
            provider=channel.provider,
            agent_id=data.get("agent_id") or channel.agent_id,
            tool_id=data.get("tool_id", channel.tool_id),
        )

    secret = data.pop("verify_secret", None)
    verify_token = data.pop("verify_token", None)
    for key, value in data.items():
        setattr(channel, key, value)
    if secret:
        channel.verify_secret_enc = encrypt_channel_secret(channel, secret)
    if verify_token:
        channel.verify_token_enc = encrypt_channel_secret(channel, verify_token)
    await db.flush()
    return to_out(channel, _public_base(request)[0])


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin),
) -> Response:
    channel = await _get_channel(db, user, channel_id)
    await db.delete(channel)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/channels/{channel_id}/test", response_model=InboundTestOut)
async def test_channel(
    channel_id: uuid.UUID,
    payload: InboundTestIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin),
) -> InboundTestOut:
    """Inject a synthetic message and run it end to end (no phone needed).

    Signature verification is skipped on purpose — the caller is an authenticated
    admin, and the whole point is to exercise the parse + run + reply path.
    """
    channel = await _get_channel(db, user, channel_id)
    if not channel.is_active:
        raise AppError(code="inbound.channel_disabled", status_code=409)

    message = IncomingMessage(
        external_id=f"test:{uuid.uuid4().hex}",
        from_id=payload.from_id,
        chat_id=payload.chat_id,
        text=payload.text,
        provider=channel.provider,
        raw={"test": True},
    )
    status, plan = await accept_message(channel, message)
    if plan is None:
        return InboundTestOut(ok=False, status=status)

    outcome = await execute_plan_full(plan)
    return InboundTestOut(
        ok=outcome.run_status == "completed",
        status=status,
        run_id=plan.run_id,
        run_status=outcome.run_status,
        reply_status=outcome.reply_status,
        needs_approval=outcome.run_status == "waiting_approval",
        text=outcome.text[:1000] if outcome.text else None,
    )


@router.post("/channels/{channel_id}/register-webhook", response_model=WebhookRegisterOut)
async def register_webhook(
    channel_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin),
) -> WebhookRegisterOut:
    """Call Telegram ``setWebhook`` for this channel using the tool's bot token.

    WhatsApp has no equivalent API (Meta dashboard only), so it is rejected here.
    """
    channel = await _get_channel(db, user, channel_id)
    if channel.provider != "telegram":
        raise AppError(
            code="inbound.register_unsupported",
            status_code=422,
            params={"provider": channel.provider},
        )
    if channel.tool_id is None:
        raise AppError(code="inbound.reply_tool_required", status_code=422)
    tool = await db.get(Tool, channel.tool_id)
    if tool is None:
        raise NotFoundError(code="tool.not_found")
    token = decrypt_tool_secret(tool)
    if not token:
        raise AppError(code="tool.secret_missing", status_code=422)
    verify_secret = decrypt_channel_secret(channel)
    if not verify_secret:
        raise AppError(code="inbound.secret_required", status_code=422)

    base, configured = _public_base(request)
    url = f"{base}{_paths(channel)[0]}"
    detail: str | None = None
    ok = False
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=20.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={
                    "url": url,
                    "secret_token": verify_secret,
                    "allowed_updates": ["message"],
                },
            )
        payload = response.json()
        ok = bool(payload.get("ok"))
        detail = str(payload.get("description") or "")[:300] or None
    except Exception as exc:  # noqa: BLE001 - a network failure is just "not ok"
        detail = f"{type(exc).__name__}: {exc}"[:300]

    log.info("inbound.register_webhook", channel=channel.slug, ok=ok, url=url)
    return WebhookRegisterOut(ok=ok, url=url, detail=detail, public_base_url=configured)


@router.get("/channels/{channel_id}/events", response_model=list[InboundEventOut])
async def list_channel_events(
    channel_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[InboundEventOut]:
    channel = await _get_channel(db, user, channel_id)
    rows = (
        (
            await db.execute(
                select(InboundEvent)
                .where(
                    InboundEvent.channel_id == channel.id,
                    InboundEvent.org_id == user.org_id,
                )
                .order_by(InboundEvent.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [InboundEventOut.model_validate(row) for row in rows]


