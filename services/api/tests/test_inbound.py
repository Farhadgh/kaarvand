"""Inbound webhooks: signature checks, idempotency, run creation, auto-reply."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any

import httpx
import respx
from sqlalchemy import func, select

from app.db.models import InboundChannel, InboundEvent, Run
from app.db.session import session_scope

PROMPT_KEY = "agent.system.default"
TG_SEND = "https://api.telegram.org/bot"
WA_SEND = "https://graph.facebook.com/v21.0"


async def make_agent(
    client: Any, headers: dict[str, str], *, with_model: bool = False
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"کانال‌دار {uuid.uuid4().hex[:5]}",
        "system_prompt_key": PROMPT_KEY,
    }
    if with_model:
        base = "https://api.inbound.test/v1"
        provider = (
            await client.post(
                "/v1/providers",
                headers=headers,
                json={
                    "name": f"inb-{uuid.uuid4().hex[:6]}",
                    "kind": "openai_compatible",
                    "base_url": base,
                    "api_key": "sk-inbound",
                },
            )
        ).json()
        respx.get(f"{base}/models").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "inb-model",
                            "context_length": 8000,
                            "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                        }
                    ]
                },
            )
        )
        await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=headers)
        await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=headers)
        models = (
            await client.get(
                "/v1/models", params={"provider_id": provider["id"]}, headers=headers
            )
        ).json()
        payload["model_id"] = models[0]["id"]

    response = await client.post("/v1/agents", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def make_channel(
    client: Any,
    headers: dict[str, str],
    *,
    agent_id: str,
    provider: str = "telegram",
    reply_mode: str = "off",
    tool_id: str | None = None,
    secret: str = "s3cret-token",
    verify_token: str | None = "verify-me",
    is_active: bool = True,
) -> dict[str, Any]:
    response = await client.post(
        "/v1/channels",
        headers=headers,
        json={
            "name_fa": f"کانال {provider}",
            "provider": provider,
            "agent_id": agent_id,
            "tool_id": tool_id,
            "reply_mode": reply_mode,
            "verify_secret": secret,
            "verify_token": verify_token if provider == "whatsapp" else None,
            "is_active": is_active,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def telegram_update(update_id: int, text: str = "سلام", chat_id: int = 555) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": chat_id, "is_bot": False},
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


def whatsapp_payload(message_id: str, text: str = "سلام", sender: str = "989120000000") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": sender,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ]
                        },
                    }
                ],
            }
        ],
    }


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ------------------------------------------------------------------- creation
async def test_channel_is_created_without_leaking_secrets(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    channel = await make_channel(
        client, auth_headers, agent_id=agent["id"], provider="whatsapp", reply_mode="auto"
    )

    assert channel["slug"].startswith("whatsapp-")
    assert channel["has_secret"] is True
    assert channel["has_verify_token"] is True
    assert channel["webhook_path"] == f"/v1/inbound/whatsapp/{channel['slug']}"
    assert "s3cret-token" not in json.dumps(channel)
    assert "verify-me" not in json.dumps(channel)

    listed = (await client.get("/v1/channels", headers=auth_headers)).json()
    assert [row["id"] for row in listed] == [channel["id"]]


async def test_channel_requires_secret_and_verify_token(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)

    no_secret = await client.post(
        "/v1/channels",
        headers=auth_headers,
        json={"name_fa": "بی‌رمز", "provider": "telegram", "agent_id": agent["id"]},
    )
    assert no_secret.status_code == 422
    assert no_secret.json()["error"]["code"] == "inbound.secret_required"

    no_token = await client.post(
        "/v1/channels",
        headers=auth_headers,
        json={
            "name_fa": "بی‌توکن",
            "provider": "whatsapp",
            "agent_id": agent["id"],
            "verify_secret": "app-secret",
        },
    )
    assert no_token.status_code == 422
    assert no_token.json()["error"]["code"] == "inbound.verify_token_required"


async def test_reply_tool_must_match_the_provider(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    installed = (
        await client.post(
            "/v1/apps/whatsapp/install",
            headers=auth_headers,
            json={
                "agent_id": agent["id"],
                "secret": "wa-token",
                "variables": {"phone_number_id": "123"},
            },
        )
    ).json()

    mismatch = await client.post(
        "/v1/channels",
        headers=auth_headers,
        json={
            "name_fa": "ناسازگار",
            "provider": "telegram",
            "agent_id": agent["id"],
            "tool_id": installed["tool_id"],
            "verify_secret": "x",
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "inbound.tool_provider_mismatch"


async def test_custom_reply_tool_without_app_slug_is_accepted(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    tool = (
        await client.post(
            "/v1/tools",
            headers=auth_headers,
            json={
                "slug": f"custom.reply.{uuid.uuid4().hex[:6]}",
                "name_fa": "پاسخ سفارشی",
                "kind": "http",
                "input_schema": {"type": "object", "properties": {}},
                "config": {
                    "method": "POST",
                    "url": "https://api.custom.test/send",
                    "allowed_domains": ["api.custom.test"],
                    "body": {"text": "{{text}}"},
                },
                "risk_level": "low",
                "approval_policy": "auto",
            },
        )
    ).json()

    channel = await make_channel(
        client, auth_headers, agent_id=agent["id"], tool_id=tool["id"], reply_mode="auto"
    )
    assert channel["tool_id"] == tool["id"]
    assert channel["reply_mode"] == "auto"


async def test_viewer_cannot_create_channel(
    client: Any, auth_headers: dict[str, str], viewer_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    response = await client.post(
        "/v1/channels",
        headers=viewer_headers,
        json={
            "name_fa": "بیننده",
            "provider": "telegram",
            "agent_id": agent["id"],
            "verify_secret": "x",
        },
    )
    assert response.status_code == 403


# -------------------------------------------------------------------- webhooks
async def test_telegram_rejects_wrong_secret_and_unknown_slug(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    channel = await make_channel(client, auth_headers, agent_id=agent["id"])

    bad = await client.post(
        f"/v1/inbound/telegram/{channel['slug']}",
        json=telegram_update(1),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "inbound.invalid_signature"

    missing = await client.post(f"/v1/inbound/telegram/{channel['slug']}", json=telegram_update(1))
    assert missing.status_code == 401

    unknown = await client.post(
        "/v1/inbound/telegram/telegram-nope",
        json=telegram_update(1),
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret-token"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "inbound.channel_not_found"


async def test_telegram_webhook_creates_one_run_per_update(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any], monkeypatch: Any
) -> None:
    from app.api.v1 import inbound as inbound_api

    scheduled: list[Any] = []
    monkeypatch.setattr(inbound_api, "_schedule", lambda plan: scheduled.append(plan))

    agent = await make_agent(client, auth_headers)
    channel = await make_channel(client, auth_headers, agent_id=agent["id"])
    headers = {"X-Telegram-Bot-Api-Secret-Token": "s3cret-token"}
    url = f"/v1/inbound/telegram/{channel['slug']}"

    first = await client.post(url, json=telegram_update(101, "سلام"), headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "accepted"
    assert body["run_id"]

    # Telegram retries the same update until it gets a 200: must not double-run
    again = await client.post(url, json=telegram_update(101, "سلام"), headers=headers)
    assert again.status_code == 200
    assert again.json()["status"] == "duplicate"
    assert again.json()["run_id"] is None

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    async with session_scope(org_id=org_id) as db:
        runs = (
            await db.execute(select(func.count(Run.id)).where(Run.trigger == "webhook"))
        ).scalar_one()
        events = (
            (
                await db.execute(
                    select(InboundEvent).where(
                        InboundEvent.channel_id == uuid.UUID(channel["id"])
                    )
                )
            )
            .scalars()
            .all()
        )
        stored = await db.get(InboundChannel, uuid.UUID(channel["id"]))
    assert runs == 1
    assert len(events) == 1
    assert events[0].run_id is not None
    assert events[0].text == "سلام"
    assert stored.events_count == 1
    assert stored.last_event_at is not None
    assert len(scheduled) == 1
    assert scheduled[0].input_text == "سلام"
    assert scheduled[0].chat_id == "555"

    listed = (
        await client.get(f"/v1/channels/{channel['id']}/events", headers=auth_headers)
    ).json()
    assert listed[0]["status"] == "accepted"
    assert listed[0]["external_id"] == "tg:101"


async def test_telegram_ignores_non_text_updates(
    client: Any, auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    from app.api.v1 import inbound as inbound_api

    monkeypatch.setattr(inbound_api, "_schedule", lambda plan: None)

    agent = await make_agent(client, auth_headers)
    channel = await make_channel(client, auth_headers, agent_id=agent["id"])
    payload = {
        "update_id": 7,
        "message": {"message_id": 7, "chat": {"id": 1}, "sticker": {"file_id": "x"}},
    }
    response = await client.post(
        f"/v1/inbound/telegram/{channel['slug']}",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["run_id"] is None


async def test_disabled_channel_accepts_but_does_not_run(
    client: Any, auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    from app.api.v1 import inbound as inbound_api

    monkeypatch.setattr(inbound_api, "_schedule", lambda plan: None)

    agent = await make_agent(client, auth_headers)
    channel = await make_channel(client, auth_headers, agent_id=agent["id"], is_active=False)
    response = await client.post(
        f"/v1/inbound/telegram/{channel['slug']}",
        json=telegram_update(9),
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"


async def test_whatsapp_handshake_and_signature(
    client: Any, auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    from app.api.v1 import inbound as inbound_api

    monkeypatch.setattr(inbound_api, "_schedule", lambda plan: None)

    agent = await make_agent(client, auth_headers)
    channel = await make_channel(
        client, auth_headers, agent_id=agent["id"], provider="whatsapp", secret="app-secret"
    )
    path = f"/v1/inbound/whatsapp/{channel['slug']}"

    ok = await client.get(
        path,
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"},
    )
    assert ok.status_code == 200
    assert ok.text == "42"

    denied = await client.get(
        path, params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "inbound.invalid_verify_token"

    body = json.dumps(whatsapp_payload("wamid.1")).encode()
    unsigned = await client.post(path, content=body, headers={"Content-Type": "application/json"})
    assert unsigned.status_code == 401

    signed = await client.post(
        path,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sign("app-secret", body),
        },
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "accepted"
    assert signed.json()["run_id"]


# ---------------------------------------------------------------- end to end
def sse_text(text: str) -> str:
    events = [
        {"choices": [{"delta": {"content": text}}]},
        {"usage": {"prompt_tokens": 6, "completion_tokens": 4}},
    ]
    body = "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)
    return body + "data: [DONE]\n\n"


@respx.mock
async def test_auto_reply_runs_the_agent_and_answers_the_sender(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    from app.core.config import get_settings
    from app.runtime.inbound import IncomingMessage, accept_message, execute_plan

    agent = await make_agent(client, auth_headers, with_model=True)
    installed = (
        await client.post(
            "/v1/apps/telegram/install",
            headers=auth_headers,
            json={
                "agent_id": agent["id"],
                "secret": "123456:bot-token",
                "variables": {"chat_id": "-100"},
            },
        )
    ).json()
    channel = await make_channel(
        client,
        auth_headers,
        agent_id=agent["id"],
        tool_id=installed["tool_id"],
        reply_mode="auto",
    )

    respx.post("https://api.inbound.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("بله، موجود است."))
    )
    send_route = respx.post(url__regex=r"https://api\.telegram\.org/bot.*/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 11}})
    )

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    async with session_scope(org_id=org_id) as db:
        row = await db.get(InboundChannel, uuid.UUID(channel["id"]))
    assert row is not None

    status, plan = await accept_message(
        row,
        IncomingMessage(
            external_id="tg:900",
            from_id="555",
            chat_id="555",
            text="این محصول موجود است؟",
            provider="telegram",
            raw={},
        ),
    )
    assert status == "accepted"
    assert plan is not None

    reply_status = await execute_plan(plan, settings=get_settings())
    assert reply_status == "sent"
    assert send_route.called
    assert "555" in send_route.calls[0].request.content.decode()

    async with session_scope(org_id=org_id) as db:
        event = await db.get(InboundEvent, plan.event_id)
        run = await db.get(Run, plan.run_id)
    assert event is not None and event.reply_status == "sent"
    assert event.status == "completed"
    assert run is not None and run.status == "completed"
    assert run.trigger == "webhook"
    assert run.tokens_in == 6


async def test_reply_failure_is_reported_not_swallowed(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    """A 5xx from the messenger must not be recorded as `sent`."""
    from app.runtime.inbound import deliver_reply

    agent = await make_agent(client, auth_headers)
    tool = (
        await client.post(
            "/v1/tools",
            headers=auth_headers,
            json={
                "slug": f"echo.reply.{uuid.uuid4().hex[:6]}",
                "name_fa": "پاسخ محلی",
                "kind": "http",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "chat_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["chat_id", "text"],
                },
                "config": {
                    "method": "POST",
                    "url": "https://api.broken.test/sendMessage",
                    "allowed_domains": ["api.broken.test"],
                    "body": {"chat_id": "{{chat_id}}", "text": "{{text}}"},
                    "auth": {"type": "none"},
                },
                "risk_level": "medium",
                "approval_policy": "confirm",
            },
        )
    ).json()
    assert tool["id"], tool

    with respx.mock:
        respx.post("https://api.broken.test/sendMessage").mock(
            return_value=httpx.Response(502, json={"error": "upstream"})
        )
        status = await deliver_reply(
            org_id=uuid.UUID(admin_tokens["user"]["org_id"]),
            tool_id=uuid.UUID(tool["id"]),
            provider="telegram",
            chat_id="555",
            text="سلام",
        )
    assert status == "failed"
    _ = agent


async def test_reply_without_tool_is_skipped(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    from app.runtime.inbound import deliver_reply

    status = await deliver_reply(
        org_id=uuid.UUID(admin_tokens["user"]["org_id"]),
        tool_id=None,
        provider="telegram",
        chat_id="1",
        text="hi",
    )
    assert status == "no_tool"


def test_reply_args_match_each_provider() -> None:
    from app.runtime.inbound import reply_args

    assert reply_args("telegram", "42", "سلام") == {"chat_id": "42", "text": "سلام"}
    assert reply_args("whatsapp", "98912", "سلام") == {"to": "98912", "text": "سلام"}
    assert len(reply_args("telegram", "42", "x" * 5000)["text"]) == 3500


# ------------------------------------------------------------- test buttons
async def _install_telegram_tool(
    client: Any, headers: dict[str, str], agent_id: str, token: str = "123456:bot-token"
) -> str:
    installed = (
        await client.post(
            "/v1/apps/telegram/install",
            headers=headers,
            json={"agent_id": agent_id, "secret": token},
        )
    ).json()
    assert installed["tool_id"], installed
    return str(installed["tool_id"])


async def test_channel_exposes_absolute_webhook_url(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    channel = await make_channel(client, auth_headers, agent_id=agent["id"])

    listed = (await client.get("/v1/channels", headers=auth_headers)).json()
    row = next(item for item in listed if item["id"] == channel["id"])
    assert row["webhook_url"].startswith("http")
    assert row["webhook_url"].endswith(f"/v1/inbound/telegram/{channel['slug']}")


@respx.mock
async def test_test_button_runs_the_agent_and_answers(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers, with_model=True)
    tool_id = await _install_telegram_tool(client, auth_headers, agent["id"])
    channel = await make_channel(
        client, auth_headers, agent_id=agent["id"], tool_id=tool_id, reply_mode="auto"
    )

    respx.post("https://api.inbound.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("پاسخ آزمایشی ایجنت"))
    )
    send = respx.post(url__regex=r"https://api\.telegram\.org/bot.*/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 3}})
    )

    response = await client.post(
        f"/v1/channels/{channel['id']}/test",
        headers=auth_headers,
        json={"text": "این یک تست است", "chat_id": "test-chat"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["run_status"] == "completed"
    assert body["reply_status"] == "sent"
    assert body["ok"] is True
    assert body["text"] == "پاسخ آزمایشی ایجنت"
    assert send.called

    events = (
        await client.get(f"/v1/channels/{channel['id']}/events", headers=auth_headers)
    ).json()
    assert events[0]["external_id"].startswith("test:")


async def test_test_button_refuses_disabled_channel(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    channel = await make_channel(client, auth_headers, agent_id=agent["id"], is_active=False)
    response = await client.post(
        f"/v1/channels/{channel['id']}/test", headers=auth_headers, json={}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inbound.channel_disabled"


@respx.mock
async def test_register_webhook_calls_telegram(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    tool_id = await _install_telegram_tool(client, auth_headers, agent["id"], "999:real-token")
    channel = await make_channel(client, auth_headers, agent_id=agent["id"], tool_id=tool_id)

    route = respx.post("https://api.telegram.org/bot999:real-token/setWebhook").mock(
        return_value=httpx.Response(
            200, json={"ok": True, "result": True, "description": "Webhook was set"}
        )
    )
    response = await client.post(
        f"/v1/channels/{channel['id']}/register-webhook", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["detail"] == "Webhook was set"
    assert body["url"].endswith(channel["slug"])
    assert body["public_base_url"] is False  # no APP_PUBLIC_BASE_URL in tests
    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["secret_token"] == "s3cret-token"
    assert sent["allowed_updates"] == ["message"]


async def test_register_webhook_is_telegram_only(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    channel = await make_channel(
        client, auth_headers, agent_id=agent["id"], provider="whatsapp", secret="app-secret"
    )
    response = await client.post(
        f"/v1/channels/{channel['id']}/register-webhook", headers=auth_headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "inbound.register_unsupported"





