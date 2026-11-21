"""Account links: connect a customer's own account, then act as them.

The device is faked with a ``DeviceSession`` (as in ``test_connector``), so the
whole chain runs without a browser: create link -> probe (device says "logged
in") -> tools are provisioned -> another customer sees nothing.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.connector.executor import execute_connector_tool
from app.connector.hub import DeviceSession, hub
from app.core.errors import AppError
from app.db.models import Tool, ToolInvocation
from app.db.session import session_scope


async def _customer(client: Any, org_id: str) -> tuple[dict[str, str], str]:
    import uuid as _uuid

    from app.core.security import hash_password
    from app.db.models import User

    email = f"link-{_uuid.uuid4().hex[:6]}@openbot.local"
    password = "link-pass-123"
    async with session_scope(bypass_rls=True) as db:
        db.add(
            User(
                org_id=_uuid.UUID(org_id),
                email=email,
                full_name="مشتری حساب‌ها",
                password_hash=hash_password(password),
                role="user",
            )
        )
    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    body = login.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


class FakeBridge:
    """Answers ``link.command`` frames the way the desktop bridge will."""

    def __init__(self, device_id: uuid.UUID, org_id: uuid.UUID, *, logged_in: bool = True) -> None:
        self.device_id = device_id
        self.org_id = org_id
        self.logged_in = logged_in
        self.commands: list[dict[str, Any]] = []
        self.session = DeviceSession(
            device_id=device_id, org_id=org_id, send=self.send, name="لپ‌تاپ تست"
        )

    async def send(self, payload: dict[str, Any]) -> None:
        self.commands.append(payload)
        action = payload.get("action")
        reply: dict[str, Any] = {
            "type": "link.result",
            "call_id": payload["call_id"],
            "ok": True,
        }
        if action == "probe":
            reply.update(
                {
                    "logged_in": self.logged_in,
                    "display_name": "علی رضایی" if self.logged_in else None,
                    "external_account_id": "1000001" if self.logged_in else None,
                    "detail": None if self.logged_in else "login_required",
                }
            )
        elif action == "open":
            reply["window"] = "facebook"
        hub.resolve(payload["call_id"], reply)

    def __enter__(self) -> FakeBridge:
        hub.register(self.session)
        return self

    def __exit__(self, *_: Any) -> None:
        hub.unregister(self.device_id)


async def _device(client: Any, headers: dict[str, str], name: str = "لپ‌تاپ من") -> dict[str, Any]:
    created = await client.post("/v1/devices", headers=headers, json={"name": name})
    assert created.status_code == 201, created.text
    return created.json()



async def test_provider_catalog_lists_what_each_agent_may_do(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/v1/links/providers", headers=auth_headers)
    assert response.status_code == 200, response.text
    rows = {row["slug"]: row for row in response.json()}

    assert {"facebook", "telegram_web", "whatsapp_web"} <= set(rows)
    assert rows["facebook"]["available"] is True
    assert rows["instagram"]["available"] is False
    facebook_tools = {tool["name"] for tool in rows["facebook"]["tools"]}
    assert facebook_tools == {"post", "notifications"}
    assert rows["facebook"]["tools"][0]["input_schema"]["required"] == ["text"]


async def test_create_link_without_a_device_still_creates_the_card(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    headers, _ = await _customer(client, admin_tokens["user"]["org_id"])
    response = await client.post("/v1/links", headers=headers, json={"provider": "facebook"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["auth_kind"] == "browser"
    assert body["login_opened"] is False
    assert body["device_online"] is False
    assert body["provider_title_fa"] == "فیسبوک"
    assert body["tool_slugs"] == []

    duplicate = await client.post("/v1/links", headers=headers, json={"provider": "facebook"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "link.already_exists"

    unknown = await client.post("/v1/links", headers=headers, json={"provider": "orkut"})
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "link.unknown_provider"

    soon = await client.post("/v1/links", headers=headers, json={"provider": "instagram"})
    assert soon.status_code == 422
    assert soon.json()["error"]["code"] == "link.provider_soon"


async def test_probe_activates_the_link_and_provisions_tools(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = admin_tokens["user"]["org_id"]
    headers, customer_id = await _customer(client, org_id)
    device = await _device(client, headers)

    with FakeBridge(uuid.UUID(device["id"]), uuid.UUID(org_id)) as bridge:
        created = await client.post("/v1/links", headers=headers, json={"provider": "facebook"})
        assert created.status_code == 201, created.text
        link = created.json()
        assert link["login_opened"] is True
        assert link["device_id"] == device["id"]

        probe = await client.post(f"/v1/links/{link['id']}/probe", headers=headers)
        assert probe.status_code == 200, probe.text
        body = probe.json()
        assert body["logged_in"] is True
        assert body["status"] == "active"
        assert body["display_name"] == "علی رضایی"
        assert sorted(body["tools"]) == sorted(
            [f"facebook.{link['id'][:8]}.notifications", f"facebook.{link['id'][:8]}.post"]
        )
        assert bridge.commands[0]["type"] == "link.command"
        assert bridge.commands[0]["site_url"].startswith("https://www.facebook.com")

        # the tools are ordinary connector tools owned by the customer
        tools = (await client.get("/v1/tools", headers=headers)).json()
        mine = {row["slug"]: row for row in tools if row["slug"].startswith("facebook.")}
        assert set(mine) == set(body["tools"])
        post = mine[f"facebook.{link['id'][:8]}.post"]
        assert post["kind"] == "connector"
        assert post["category"] == "social"
        assert post["approval_policy"] == "confirm"
        assert post["risk_level"] == "high"
        assert post["config"]["link_id"] == link["id"]
        assert post["config"]["device_id"] == device["id"]
        assert post["actions"][0]["op"] == "browser.goto"
        assert "{{input.text}}" in str(post["actions"])

        listed = (await client.get("/v1/links", headers=headers)).json()
        assert [row["id"] for row in listed] == [link["id"]]
        assert listed[0]["status"] == "active"
        assert listed[0]["device_online"] is True

        assets = (await client.get(f"/v1/links/{link['id']}/assets", headers=headers)).json()
        assert [row["kind"] for row in assets] == ["site"]
        assert assets[0]["external_id"] == "facebook"

        # syncing again is idempotent, not a duplicate
        again = await client.post(f"/v1/links/{link['id']}/sync", headers=headers)
        assert again.status_code == 200, again.text
        assert again.json()["count"] == 2


async def test_another_customer_cannot_see_or_drive_the_link(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = admin_tokens["user"]["org_id"]
    owner, _ = await _customer(client, org_id)
    stranger, _ = await _customer(client, org_id)
    device = await _device(client, owner)

    with FakeBridge(uuid.UUID(device["id"]), uuid.UUID(org_id)):
        link = (
            await client.post("/v1/links", headers=owner, json={"provider": "facebook"})
        ).json()

    assert (await client.get("/v1/links", headers=stranger)).json() == []
    assert (await client.get(f"/v1/links/{link['id']}", headers=stranger)).status_code == 404
    for action in ("probe", "open", "sync", "stop"):
        response = await client.post(f"/v1/links/{link['id']}/{action}", headers=stranger)
        assert response.status_code == 404, action
        assert response.json()["error"]["code"] == "link.not_found"
    assert (await client.delete(f"/v1/links/{link['id']}", headers=stranger)).status_code == 404

    # the admin still sees the whole tenant
    everything = (await client.get("/v1/links", headers=auth_headers)).json()
    assert link["id"] in [row["id"] for row in everything]


async def test_link_tools_are_private_to_their_owner(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    """The real hole this closes: binding someone else's session to your agent."""
    org_id = admin_tokens["user"]["org_id"]
    owner, _ = await _customer(client, org_id)
    stranger, _ = await _customer(client, org_id)
    device = await _device(client, owner)

    with FakeBridge(uuid.UUID(device["id"]), uuid.UUID(org_id)):
        link = (
            await client.post("/v1/links", headers=owner, json={"provider": "facebook"})
        ).json()
        await client.post(f"/v1/links/{link['id']}/probe", headers=owner)

    slug = f"facebook.{link['id'][:8]}.post"
    catalog_rows = (await client.get("/v1/tools", headers=owner)).json()
    owner_tools = {row["slug"]: row for row in catalog_rows}
    tool_id = owner_tools[slug]["id"]

    # the stranger does not even see it in the catalog
    stranger_tools = {
        row["slug"] for row in (await client.get("/v1/tools", headers=stranger)).json()
    }
    assert slug not in stranger_tools
    assert (await client.get(f"/v1/tools/{tool_id}", headers=stranger)).status_code == 404
    assert (
        await client.patch(f"/v1/tools/{tool_id}", headers=stranger, json={"name_fa": "دزدی"})
    ).status_code == 404

    # ... and cannot bind it to an agent
    agent = (
        await client.post("/v1/agents", headers=stranger, json={"name": "ایجنت مشتری دیگر"})
    ).json()
    bind = await client.put(
        f"/v1/agents/{agent['id']}/tools",
        headers=stranger,
        json=[{"tool_id": tool_id, "permission_level": "auto"}],
    )
    assert bind.status_code == 422
    assert bind.json()["error"]["code"] == "tool.not_found"



    # the owner can bind it to their own agent
    owner_agent = (
        await client.post("/v1/agents", headers=owner, json={"name": "ایجنت صاحب حساب"})
    ).json()
    mine = await client.put(
        f"/v1/agents/{owner_agent['id']}/tools",
        headers=owner,
        json=[{"tool_id": tool_id, "permission_level": "confirm"}],
    )
    assert mine.status_code == 200, mine.text


async def test_stop_pauses_and_disconnect_removes_everything(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = admin_tokens["user"]["org_id"]
    headers, _ = await _customer(client, org_id)
    device = await _device(client, headers)

    with FakeBridge(uuid.UUID(device["id"]), uuid.UUID(org_id)) as bridge:
        link = (
            await client.post("/v1/links", headers=headers, json={"provider": "telegram_web"})
        ).json()
        await client.post(f"/v1/links/{link['id']}/probe", headers=headers)

        stopped = await client.post(f"/v1/links/{link['id']}/stop", headers=headers)
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["status"] == "paused"
        assert bridge.commands[-1]["action"] == "stop"

        # a paused link cannot be re-synced until it is probed again
        blocked = await client.post(f"/v1/links/{link['id']}/sync", headers=headers)
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "link.not_active"

        removed = await client.delete(f"/v1/links/{link['id']}", headers=headers)
        assert removed.status_code == 204
        assert bridge.commands[-1]["action"] == "wipe"

    assert (await client.get("/v1/links", headers=headers)).json() == []
    async with session_scope(org_id=uuid.UUID(org_id)) as db:
        left = (
            (await db.execute(select(Tool).where(Tool.slug.like("telegram_web.%"))))
            .scalars()
            .all()
        )
        assert left == []


async def test_a_customer_cannot_use_the_admins_device(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    """Routing a customer's browser session to another laptop must be impossible."""
    org_id = admin_tokens["user"]["org_id"]
    admin_device = await _device(client, auth_headers, name="لپ‌تاپ ادمین")
    headers, _ = await _customer(client, org_id)

    with FakeBridge(uuid.UUID(admin_device["id"]), uuid.UUID(org_id)):
        created = await client.post("/v1/links", headers=headers, json={"provider": "facebook"})
        assert created.status_code == 201, created.text
        assert created.json()["login_opened"] is False
        assert created.json()["device_id"] is None

        probe = await client.post(f"/v1/links/{created.json()['id']}/probe", headers=headers)
        assert probe.status_code == 409
        assert probe.json()["error"]["code"] == "link.device_offline"

    devices = (await client.get("/v1/devices", headers=headers)).json()
    assert admin_device["id"] not in [row["id"] for row in devices]


async def test_probe_reports_when_the_customer_is_not_logged_in(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = admin_tokens["user"]["org_id"]
    headers, _ = await _customer(client, org_id)
    device = await _device(client, headers)

    with FakeBridge(uuid.UUID(device["id"]), uuid.UUID(org_id), logged_in=False):
        link = (
            await client.post("/v1/links", headers=headers, json={"provider": "facebook"})
        ).json()
        probe = await client.post(f"/v1/links/{link['id']}/probe", headers=headers)

    assert probe.status_code == 200, probe.text
    body = probe.json()
    assert body["logged_in"] is False
    assert body["status"] == "pending"
    assert body["tools"] == []
    assert body["hint_fa"]
    refreshed = (await client.get(f"/v1/links/{link['id']}", headers=headers)).json()
    assert refreshed["status"] == "pending"
    assert refreshed["last_error"] == "link.login_required"


async def test_link_tool_respects_the_hourly_ceiling(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    """A linked account is a personal session: the ceiling is not optional."""
    org_id = admin_tokens["user"]["org_id"]
    headers, _ = await _customer(client, org_id)
    device = await _device(client, headers)

    with FakeBridge(uuid.UUID(device["id"]), uuid.UUID(org_id)):
        link = (
            await client.post("/v1/links", headers=headers, json={"provider": "facebook"})
        ).json()
        await client.post(f"/v1/links/{link['id']}/probe", headers=headers)

    slug = f"facebook.{link['id'][:8]}.post"
    rows = {row["slug"]: row for row in (await client.get("/v1/tools", headers=headers)).json()}
    tool_id = uuid.UUID(rows[slug]["id"])

    async with session_scope(org_id=uuid.UUID(org_id)) as db:
        tool = await db.get(Tool, tool_id)
        assert tool is not None
        tool.config = {**(tool.config or {}), "rate_limit_per_hour": 1}
        db.add(
            ToolInvocation(
                org_id=uuid.UUID(org_id),
                tool_id=tool_id,
                tool_slug=slug,
                args={"text": "پست قبلی"},
                result={},
                status="ok",
                risk_level="high",
            )
        )
        await db.flush()

    async with session_scope(org_id=uuid.UUID(org_id)) as db:
        tool = await db.get(Tool, tool_id)
        with pytest.raises(AppError) as exc:
            await execute_connector_tool(
                db, tool=tool, args={"text": "پست تازه"}, org_id=uuid.UUID(org_id)
            )
    assert exc.value.code == "tool.rate_limited"

