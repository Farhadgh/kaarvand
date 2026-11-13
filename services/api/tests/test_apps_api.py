"""App catalog: listing, install/uninstall, device scan, cloning templates."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select

from app.connector.hub import DeviceSession, hub
from app.core.errors import AppError
from app.db.models import AgentTool, AppCatalog
from app.db.session import session_scope
from app.seeding.apps_seed import APPS

PROMPT_KEY = "agent.system.default"


async def _agent(client: Any, auth_headers: dict[str, str], name: str = "دستیار فروش") -> str:
    response = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={"name": f"{name}-{uuid.uuid4().hex[:5]}", "system_prompt_key": PROMPT_KEY},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_catalog_is_seeded_with_brand_icons(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/v1/apps", headers=auth_headers)
    assert response.status_code == 200
    apps = {row["slug"]: row for row in response.json()}

    for slug in ("telegram", "whatsapp", "instagram", "x", "excel", "outlook", "telegram_desktop"):
        assert slug in apps, slug

    assert apps["telegram"]["icon"] == "si:telegram"
    assert apps["telegram"]["runtime"] == "cloud"
    assert apps["excel"]["runtime"] == "desktop"
    assert apps["excel"]["requires_device"] is True
    for row in apps.values():
        assert ":" in row["icon"], row["slug"]
        assert row["color"] is None or row["color"].startswith("#")


async def test_seed_apps_is_idempotent(client: Any, auth_headers: dict[str, str]) -> None:
    """Re-seeding must sync existing rows (not crash and not duplicate)."""
    from sqlalchemy import func as sql_func

    from app.seeding.defaults import seed_apps

    async with session_scope(bypass_rls=True) as db:
        created = await seed_apps(db)
        total = (await db.execute(select(sql_func.count(AppCatalog.id)))).scalar_one()

    assert created == 0  # everything already seeded by conftest
    assert total == len(APPS)
    listed = (await client.get("/v1/apps", headers=auth_headers)).json()
    assert len(listed) == len(APPS)


async def test_catalog_filters_by_category_and_runtime(
    client: Any, auth_headers: dict[str, str]
) -> None:
    social = (
        await client.get("/v1/apps", params={"category": "social"}, headers=auth_headers)
    ).json()
    assert social and all(row["category"] == "social" for row in social)

    desktop = (
        await client.get("/v1/apps", params={"runtime": "desktop"}, headers=auth_headers)
    ).json()
    assert desktop and all(row["runtime"] == "desktop" for row in desktop)

    found = (await client.get("/v1/apps", params={"q": "telegram"}, headers=auth_headers)).json()
    assert {row["slug"] for row in found} == {"telegram", "telegram_desktop"}


async def test_app_detail_exposes_wizard_fields(client: Any, auth_headers: dict[str, str]) -> None:
    detail = (await client.get("/v1/apps/whatsapp", headers=auth_headers)).json()
    assert detail["tool_kind"] == "http"
    keys = {cred["key"]: cred for cred in detail["credentials"]}
    assert keys["token"]["secret"] is True
    assert keys["phone_number_id"]["required"] is True
    assert "{{phone_number_id}}" in str(detail["config_template"])

    unknown = await client.get("/v1/apps/no-such-app", headers=auth_headers)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "app.not_found"


async def test_install_creates_tool_and_binding(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent_id = await _agent(client, auth_headers)
    response = await client.post(
        "/v1/apps/whatsapp/install",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "permission_level": "confirm",
            "secret": "EAAG-demo-token",
            "variables": {"phone_number_id": "123456"},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"].startswith("whatsapp.")
    assert body["permission_level"] == "confirm"

    tools = (
        await client.get("/v1/tools", params={"enabled_only": "false"}, headers=auth_headers)
    ).json()
    tool = next(row for row in tools if row["id"] == body["tool_id"])
    assert tool["has_secret"] is True
    assert tool["secret_masked"]
    assert "EAAG-demo-token" not in str(tool)
    # wizard value landed in the config, runtime placeholders stayed intact
    assert tool["config"]["base_url"].endswith("/123456")
    assert tool["config"]["body"]["to"] == "{{to}}"
    assert tool["config"]["auth"]["type"] == "bearer"
    assert tool["config"]["app_slug"] == "whatsapp"
    assert tool["approval_policy"] == "confirm"
    assert tool["category"] == "social"

    bindings = (await client.get(f"/v1/agents/{agent_id}/tools", headers=auth_headers)).json()
    assert [row["tool_id"] for row in bindings] == [body["tool_id"]]

    again = await client.post(
        "/v1/apps/whatsapp/install",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "permission_level": "auto",
            "secret": "EAAG-rotated",
            "variables": {"phone_number_id": "123456"},
        },
    )
    assert again.status_code == 201
    assert again.json()["tool_id"] == body["tool_id"]

    # one tool per (app, agent), even after re-installing
    after = (
        await client.get("/v1/tools", params={"enabled_only": "false"}, headers=auth_headers)
    ).json()
    mine = [
        row
        for row in after
        if (row.get("config") or {}).get("app_slug") == "whatsapp"
        and row["slug"].endswith(agent_id[:8])
    ]
    assert len(mine) == 1

    catalog = {
        row["slug"]: row for row in (await client.get("/v1/apps", headers=auth_headers)).json()
    }
    assert catalog["whatsapp"]["installed_tools"] >= 1
    assert catalog["whatsapp"]["installed_agents"] >= 1


async def test_install_validates_credentials(client: Any, auth_headers: dict[str, str]) -> None:
    agent_id = await _agent(client, auth_headers)

    missing_secret = await client.post(
        "/v1/apps/telegram/install",
        headers=auth_headers,
        json={"agent_id": agent_id, "variables": {"chat_id": "-100"}},
    )
    assert missing_secret.status_code == 422
    assert missing_secret.json()["error"]["code"] == "app.missing_secret"

    missing_field = await client.post(
        "/v1/apps/whatsapp/install",
        headers=auth_headers,
        json={"agent_id": agent_id, "secret": "tok"},
    )
    assert missing_field.status_code == 422
    error = missing_field.json()["error"]
    assert error["code"] == "app.missing_field"
    assert error["params"]["field"] == "phone_number_id"


async def test_desktop_app_needs_online_device(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent_id = await _agent(client, auth_headers)

    no_device = await client.post(
        "/v1/apps/excel/install", headers=auth_headers, json={"agent_id": agent_id}
    )
    assert no_device.status_code == 422
    assert no_device.json()["error"]["code"] == "app.device_required"

    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "PC اکسل"})
    ).json()
    offline = await client.post(
        "/v1/apps/excel/install",
        headers=auth_headers,
        json={"agent_id": agent_id, "device_id": device["id"]},
    )
    assert offline.status_code == 409
    assert offline.json()["error"]["code"] == "app.device_offline"


async def test_scan_maps_detected_executables_to_catalog(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "PC فروش"})
    ).json()

    captured: dict[str, Any] = {}

    async def send(payload: dict[str, Any]) -> None:
        captured.update(payload)
        hub.resolve(
            payload["call_id"],
            {
                "type": "apps.result",
                "call_id": payload["call_id"],
                "ok": True,
                "apps": [
                    {"exe": "EXCEL.EXE", "prog_id": "Excel.Application"},
                    {"exe": "telegram.exe", "prog_id": None},
                    {"exe": "notepad.exe", "prog_id": None},
                ],
            },
        )

    hub.register(
        DeviceSession(
            device_id=uuid.UUID(device["id"]), org_id=org_id, send=send, manifest={"ops": []}
        )
    )
    try:
        response = await client.post(
            f"/v1/devices/{device['id']}/scan-apps", headers=auth_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert captured["type"] == "apps.scan"
        assert any(entry["slug"] == "excel" for entry in captured["catalog"])
        assert body["found"] == 2  # notepad.exe is not in the catalog
        slugs = {row["app_slug"] for row in body["apps"]}
        assert slugs == {"excel", "telegram_desktop"}
        assert all(row["in_catalog"] for row in body["apps"])
        assert all(row["is_granted"] is False for row in body["apps"])

        grant = await client.patch(
            f"/v1/devices/{device['id']}/apps/excel",
            headers=auth_headers,
            json={"is_granted": True},
        )
        assert grant.status_code == 200
        assert grant.json()["is_granted"] is True

        listed = (
            await client.get(f"/v1/devices/{device['id']}/apps", headers=auth_headers)
        ).json()
        assert next(row for row in listed if row["app_slug"] == "excel")["is_granted"] is True
    finally:
        hub.unregister(uuid.UUID(device["id"]))


async def test_scan_of_offline_device_is_rejected(
    client: Any, auth_headers: dict[str, str]
) -> None:
    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "PC خاموش"})
    ).json()
    response = await client.post(f"/v1/devices/{device['id']}/scan-apps", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "app.device_offline"


async def test_uninstall_removes_tool_and_binding(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent_id = await _agent(client, auth_headers)
    installed = (
        await client.post(
            "/v1/apps/x/install",
            headers=auth_headers,
            json={"agent_id": agent_id, "secret": "bearer-token", "permission_level": "deny"},
        )
    ).json()

    removed = await client.delete(
        "/v1/apps/x/install", params={"agent_id": agent_id}, headers=auth_headers
    )
    assert removed.status_code == 204

    tools = (
        await client.get("/v1/tools", params={"enabled_only": "false"}, headers=auth_headers)
    ).json()
    assert installed["tool_id"] not in {row["id"] for row in tools}

    again = await client.delete(
        "/v1/apps/x/install", params={"agent_id": agent_id}, headers=auth_headers
    )
    assert again.status_code == 404
    assert again.json()["error"]["code"] == "app.not_installed"


async def test_clone_makes_global_tool_editable(
    client: Any, auth_headers: dict[str, str]
) -> None:
    tools = (
        await client.get("/v1/tools", params={"enabled_only": "false"}, headers=auth_headers)
    ).json()
    global_tool = next(row for row in tools if row["org_id"] is None)

    clone = await client.post(f"/v1/tools/{global_tool['id']}/clone", headers=auth_headers)
    assert clone.status_code == 201, clone.text
    body = clone.json()
    assert body["org_id"] is not None
    assert body["slug"].startswith(global_tool["slug"])
    assert body["has_secret"] is False

    patched = await client.patch(
        f"/v1/tools/{body['id']}",
        headers=auth_headers,
        json={"approval_policy": "deny", "is_enabled": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["approval_policy"] == "deny"


async def test_customer_can_install_app(
    client: Any, auth_headers: dict[str, str], viewer_headers: dict[str, str]
) -> None:
    agent_id = await _agent(client, auth_headers)
    response = await client.post(
        "/v1/apps/telegram/install",
        headers=viewer_headers,
        json={"agent_id": agent_id, "secret": "tok", "variables": {"chat_id": "-1"}},
    )
    assert response.status_code in (200, 201), response.text


def test_tool_slug_is_stable_per_agent() -> None:
    from app.api.v1.apps import tool_slug_for

    class _App:
        slug = "telegram"

    agent_id = uuid.uuid4()
    assert tool_slug_for(_App(), agent_id) == f"telegram.{str(agent_id)[:8]}"


def test_new_connector_ops_are_validated() -> None:
    from app.tools.actions import OPS, validate_actions

    for op in ("app.launch", "app.windows", "ui.invoke", "clipboard.set", "keyboard.hotkey"):
        assert op in OPS

    with pytest.raises(AppError) as exc:
        validate_actions([{"op": "app.launch"}])
    assert exc.value.code == "tool.invalid_actions"

    assert validate_actions([{"op": "app.launch", "app": "excel"}]) == [
        {"op": "app.launch", "app": "excel"}
    ]


async def test_installed_tool_is_visible_to_the_model(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent_id = await _agent(client, auth_headers)
    await client.post(
        "/v1/apps/telegram/install",
        headers=auth_headers,
        json={"agent_id": agent_id, "secret": "tok", "variables": {"chat_id": "-5"}},
    )

    schemas = (
        await client.get(
            "/v1/tools/llm-schemas", params={"agent_id": agent_id}, headers=auth_headers
        )
    ).json()
    names = {row["name"] for row in schemas}
    assert f"telegram_{str(agent_id)[:8]}" in names

    async with session_scope(org_id=uuid.UUID(admin_tokens["user"]["org_id"])) as db:
        count = (
            await db.execute(
                select(func.count(AgentTool.id)).where(
                    AgentTool.agent_id == uuid.UUID(agent_id)
                )
            )
        ).scalar_one()
    assert count == 1



