"""Inbound webhook processing: verify -> dedupe -> run -> optionally reply.

Everything here is provider-agnostic except two small adapters (Telegram and
WhatsApp Cloud API). The accepted message becomes a **normal run**
(`trigger="webhook"`), so budgets, approvals, cost and tool policy are reused.

Honest note: when a run parks in ``waiting_approval`` (a tool needs a human),
no reply is sent — a person approves the run and then replies from the panel.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.crypto import get_secret_box
from app.core.deps import ADMIN_ROLE
from app.core.errors import AppError
from app.db.models import InboundChannel, InboundEvent, Tool, User
from app.db.session import session_scope
from app.runtime.starter import create_run, run_to_result
from app.tools.service import execute_tool

MAX_TEXT = 4000
REPLY_LIMIT = 3500


# --------------------------------------------------------------------- helpers
def channel_aad(channel: InboundChannel) -> str:
    return f"inbound:{channel.slug}"


def encrypt_channel_secret(channel: InboundChannel, value: str | None) -> bytes | None:
    if not value:
        return None
    return get_secret_box().encrypt(value, aad=channel_aad(channel))


def decrypt_channel_secret(channel: InboundChannel) -> str | None:
    blob = channel.verify_secret_enc
    if not blob:
        return None
    return get_secret_box().decrypt(blob, aad=channel_aad(channel))


def decrypt_verify_token(channel: InboundChannel) -> str | None:
    blob = channel.verify_token_enc
    if not blob:
        return None
    return get_secret_box().decrypt(blob, aad=channel_aad(channel))


def new_slug(provider: str) -> str:
    return f"{provider}-{secrets.token_hex(4)}"


def telegram_secret_ok(channel: InboundChannel, header_value: str | None) -> bool:
    expected = decrypt_channel_secret(channel)
    if not expected:
        return False
    return hmac.compare_digest(expected, str(header_value or ""))


def whatsapp_signature_ok(channel: InboundChannel, raw_body: bytes, header: str | None) -> bool:
    expected = decrypt_channel_secret(channel)
    if not expected:
        return False
    provided = str(header or "").strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    digest = hmac.new(expected.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, provided.lower())


# ---------------------------------------------------------------- normalisation
@dataclass(frozen=True)
class IncomingMessage:
    external_id: str
    from_id: str
    chat_id: str
    text: str
    provider: str
    raw: dict[str, Any]


def parse_telegram(payload: dict[str, Any]) -> list[IncomingMessage]:
    """Text messages only; anything else is acknowledged and ignored."""
    update_id = payload.get("update_id")
    message = payload.get("message") or payload.get("edited_message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    if not text or not chat.get("id") or update_id is None:
        return []
    sender = (message.get("from") or {}).get("id") or chat.get("id")
    return [
        IncomingMessage(
            external_id=f"tg:{update_id}",
            from_id=str(sender),
            chat_id=str(chat.get("id")),
            text=str(text)[:MAX_TEXT],
            provider="telegram",
            raw=payload,
        )
    ]


def parse_whatsapp(payload: dict[str, Any]) -> list[IncomingMessage]:
    out: list[IncomingMessage] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for item in value.get("messages") or []:
                text = ((item.get("text") or {}).get("body")) or ""
                if not text or not item.get("id"):
                    continue
                out.append(
                    IncomingMessage(
                        external_id=f"wa:{item['id']}",
                        from_id=str(item.get("from") or ""),
                        chat_id=str(item.get("from") or ""),
                        text=str(text)[:MAX_TEXT],
                        provider="whatsapp",
                        raw=payload,
                    )
                )
    return out


def reply_args(provider: str, chat_id: str, text: str) -> dict[str, Any]:
    body = text[:REPLY_LIMIT]
    if provider == "whatsapp":
        return {"to": chat_id, "text": body}
    return {"chat_id": chat_id, "text": body}


# ------------------------------------------------------------------- processing
@dataclass(frozen=True)
class InboundPlan:
    """What the caller needs to execute the run after the HTTP 200 is sent."""

    channel_id: uuid.UUID
    org_id: uuid.UUID
    run_id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    input_text: str
    chat_id: str
    reply_mode: str
    tool_id: uuid.UUID | None


async def _owner_id(db: AsyncSession, org_id: uuid.UUID) -> uuid.UUID | None:
    return (
        await db.execute(
            select(User.id)
            .where(User.org_id == org_id, User.is_active.is_(True))
            .order_by((User.role != ADMIN_ROLE), User.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()


async def accept_message(
    channel: InboundChannel, message: IncomingMessage
) -> tuple[str, InboundPlan | None]:
    """Dedupe + create the run. Returns ``(status, plan)``; the run is committed."""
    if not channel.is_active:
        return "disabled", None

    org_id = channel.org_id
    async with session_scope(org_id=org_id) as db:
        event = InboundEvent(
            org_id=org_id,
            channel_id=channel.id,
            provider=message.provider,
            external_id=message.external_id,
            status="accepted",
            from_id=message.from_id[:120],
            chat_id=message.chat_id[:120],
            text=message.text,
            payload={"provider": message.provider},
        )
        db.add(event)
        try:
            await db.flush()
        except IntegrityError:
            # the provider retried a delivery we already accepted
            await db.rollback()
            return "duplicate", None

        owner = await _owner_id(db, org_id)
        if owner is None:
            event.status = "failed"
            event.error = "org has no active user"
            return "failed", None

        run = await create_run(db, org_id=org_id, agent_id=channel.agent_id, trigger="webhook")
        event.run_id = run.id
        channel_row = await db.get(InboundChannel, channel.id)
        if channel_row is not None:
            channel_row.last_event_at = datetime.now(UTC)
            channel_row.events_count = int(channel_row.events_count or 0) + 1
        plan = InboundPlan(
            channel_id=channel.id,
            org_id=org_id,
            run_id=run.id,
            user_id=owner,
            event_id=event.id,
            input_text=message.text,
            chat_id=message.chat_id,
            reply_mode=channel.reply_mode,
            tool_id=channel.tool_id,
        )
    return "accepted", plan


async def deliver_reply(
    *,
    org_id: uuid.UUID,
    tool_id: uuid.UUID | None,
    provider: str,
    chat_id: str,
    text: str,
    run_id: uuid.UUID | None = None,
) -> str:
    """Send the answer back through the channel's installed app tool."""
    if not tool_id:
        return "no_tool"
    if not text.strip():
        return "empty"
    async with session_scope(org_id=org_id) as db:
        tool = await db.get(Tool, tool_id)
        if tool is None or not tool.is_enabled:
            return "no_tool"
        try:
            outcome = await execute_tool(
                db,
                tool=tool,
                args=reply_args(provider, chat_id, text),
                org_id=org_id,
                run_id=run_id,
                # no human in the loop on a webhook: the channel owner opted in
                # with reply_mode="auto" and the call is audited in tool_invocations
                force=True,
            )
        except AppError as exc:
            return f"error:{exc.code}"[:16]
        except Exception:  # noqa: BLE001 - provider hiccups must not break the run
            return "error"
        result = outcome.get("result") or {}
        # http tools never raise on 4xx/5xx: they report ok=False
        if isinstance(result, dict) and result.get("ok") is False:
            return "failed"
    return "sent"


@dataclass(frozen=True)
class ExecutedInbound:
    """Outcome of one inbound run (used by the webhook path and the test button)."""

    run_status: str
    reply_status: str
    text: str


async def execute_plan_full(
    plan: InboundPlan, *, settings: Settings | None = None
) -> ExecutedInbound:
    """Run the agent and (when allowed) answer the sender."""
    settings = settings or get_settings()
    result = await run_to_result(
        org_id=plan.org_id,
        run_id=plan.run_id,
        user_id=plan.user_id,
        settings=settings,
        input_text=plan.input_text,
    )
    reply_status = "skipped"
    provider = "telegram"
    async with session_scope(org_id=plan.org_id) as db:
        channel = await db.get(InboundChannel, plan.channel_id)
        if channel is not None:
            provider = channel.provider

    if plan.reply_mode == "auto" and result.run.status == "completed":
        reply_status = await deliver_reply(
            org_id=plan.org_id,
            tool_id=plan.tool_id,
            provider=provider,
            chat_id=plan.chat_id,
            text=result.text,
            run_id=plan.run_id,
        )
    elif plan.reply_mode == "auto":
        reply_status = f"run:{result.run.status}"[:16]

    async with session_scope(org_id=plan.org_id) as db:
        event = await db.get(InboundEvent, plan.event_id)
        if event is not None:
            event.reply_status = reply_status
            event.status = "completed" if result.run.status == "completed" else "accepted"
            if result.run.error_code:
                event.error = str(result.run.error_code)[:500]
    return ExecutedInbound(
        run_status=result.run.status,
        reply_status=reply_status,
        text=result.text,
    )


async def execute_plan(plan: InboundPlan, *, settings: Settings | None = None) -> str:
    """Thin wrapper: the webhook path only cares about the reply status."""
    outcome = await execute_plan_full(plan, settings=settings)
    return outcome.reply_status

