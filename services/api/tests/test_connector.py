"""Desktop connector: pairing, hub, script execution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.connector.executor import build_steps, execute_connector_tool
from app.connector.hub import DeviceSession, hub
from app.connector.pairing import (
    codes_match,
    is_expired,
    normalize_code,
    read_device_token,
)
from app.core.errors import AppError
from app.db.models import Device, Tool
from app.db.session import session_scope
from app.tools.service import execute_tool


def test_pairing_code_helpers() -> None:
    assert normalize_code(" ab-12 34 ") == "AB1234"
    assert codes_match("AB1234", "ab-1234")
    assert not codes_match("AB1234", "ZZZZ")
    assert not codes_match(None, "AB1234")
    assert is_expired(datetime.now(UTC) - timedelta(minutes=1))
    assert not is_expired(datetime.now(UTC) + timedelta(minutes=5))
    assert is_expired(None)


def test_build_steps_substitutes_inputs() -> None:
    steps = build_steps(
        [
            {"op": "office.open", "path": "{{input.file}}"},
            {"op": "screenshot", "save_as": "artifacts/{{run_id}}.png"},
        ],
        {"file": "D:/data/a.xlsx"},
        run_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    )
    assert steps[0]["path"] == "D:/data/a.xlsx"
    assert steps[1]["save_as"].startswith("artifacts/11111111")


async def test_create_and_pair_device(client: Any, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/v1/devices", headers=auth_headers, json={"name": "کیف پول مدیر"}
    )
    assert created.status_code == 201, created.text
    device = created.json()
    assert device["status"] == "pending"
    code = device["pairing_code"]
    assert len(code) == 8

    wrong = await client.post(
        "/v1/devices/pair", json={"code": "ZZZZZZZZ", "pubkey": "a" * 16}
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "device.invalid_code"

    paired = await client.post(
        "/v1/devices/pair",
        json={"code": code, "pubkey": "pub-key-123456", "os": "Windows", "version": "0.1.0"},
    )
    assert paired.status_code == 200, paired.text
    body = paired.json()
    assert body["device_id"] == device["id"]
    assert body["ws_url"].endswith("/v1/ws/connector")

    device_id, _org_id = read_device_token(body["device_token"])
    assert str(device_id) == device["id"]

    refreshed = (await client.get(f"/v1/devices/{device['id']}", headers=auth_headers)).json()
    assert refreshed["status"] == "paired"
    assert refreshed["os"] == "Windows"


async def test_pair_rejects_reused_code(client: Any, auth_headers: dict[str, str]) -> None:
    created = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "دستگاه تکراری"})
    ).json()
    code = created["pairing_code"]

    first = await client.post("/v1/devices/pair", json={"code": code, "pubkey": "k" * 12})
    assert first.status_code == 200
    second = await client.post("/v1/devices/pair", json={"code": code, "pubkey": "k" * 12})
    assert second.status_code == 401


async def test_device_listing_and_delete(client: Any, auth_headers: dict[str, str]) -> None:
    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "دستگاه موقت"})
    ).json()

    listed = (await client.get("/v1/devices", headers=auth_headers)).json()
    assert any(row["id"] == device["id"] for row in listed)

    patched = await client.patch(
        f"/v1/devices/{device['id']}",
        headers=auth_headers,
        json={"name": "دستگاه تغییر یافته", "allowed_paths": ["D:/data"]},
    )
    assert patched.status_code == 200
    assert patched.json()["allowed_paths"] == ["D:/data"]

    deleted = await client.delete(f"/v1/devices/{device['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/v1/devices/{device['id']}", headers=auth_headers)
    assert missing.status_code == 404


async def test_device_rotation(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "دستگاه چرخشی"})
    ).json()
    first_code = device["pairing_code"]
    rotated = await client.post(f"/v1/devices/{device['id']}/rotate-code", headers=auth_headers)
    assert rotated.status_code == 200
    assert rotated.json()["pairing_code"] != first_code

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    async with session_scope(org_id=org_id) as db:
        row = (
            await db.execute(select(Device).where(Device.id == uuid.UUID(device["id"])))
        ).scalar_one()
        assert row.status == "pending"
        assert row.pairing_expires_at is not None


async def test_execute_connector_tool_round_trip(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "اکسل منشی"})
    ).json()

    tool = (
        await client.post(
            "/v1/tools",
            headers=auth_headers,
            json={
                "slug": f"demo.conn.{uuid.uuid4().hex[:6]}",
                "name_fa": "افزودن ردیف",
                "kind": "connector",
                "input_schema": {
                    "type": "object",
                    "properties": {"sheet": {"type": "string"}},
                    "required": ["sheet"],
                },
                "actions": [{"op": "office.cells", "sheet": "{{input.sheet}}", "append": [1, 2]}],
                "risk_level": "medium",
                "approval_policy": "confirm",
            },
        )
    ).json()

    captured: dict[str, Any] = {}

    async def send(payload: dict[str, Any]) -> None:
        captured.update(payload)
        hub.resolve(
            payload["call_id"],
            {
                "type": "script.result",
                "call_id": payload["call_id"],
                "ok": True,
                "output": [{"step": 0, "simulated": True}],
            },
        )

    session = DeviceSession(
        device_id=uuid.UUID(device["id"]),
        org_id=org_id,
        send=send,
        manifest={"ops": ["office.cells"]},
    )
    hub.register(session)
    try:
        async with session_scope(org_id=org_id) as db:
            tool_row = await db.get(Tool, uuid.UUID(tool["id"]))
            result = await execute_connector_tool(
                db, tool=tool_row, args={"sheet": "Sheet1"}, org_id=org_id
            )
        assert result["steps"] == 1
        assert captured["type"] == "script.run"
        assert captured["steps"][0]["sheet"] == "Sheet1"

        ops = (await client.get(f"/v1/devices/{device['id']}/ops", headers=auth_headers)).json()
        assert ops["online"] is True
        assert ops["ops"] == ["office.cells"]

        async with session_scope(org_id=org_id) as db:
            tool_row = await db.get(Tool, uuid.UUID(tool["id"]))
            outcome = await execute_tool(
                db, tool=tool_row, args={"sheet": "Sheet1"}, org_id=org_id, force=True
            )
        assert outcome["result"]["device_id"] == device["id"]
    finally:
        hub.unregister(uuid.UUID(device["id"]))


async def test_offline_device_returns_stable_code(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    tool = (
        await client.post(
            "/v1/tools",
            headers=auth_headers,
            json={
                "slug": f"demo.offline.{uuid.uuid4().hex[:6]}",
                "name_fa": "ابزار آفلاین",
                "kind": "connector",
                "input_schema": {"type": "object", "properties": {}},
                "actions": [{"op": "screenshot"}],
                "risk_level": "low",
                "approval_policy": "auto",
            },
        )
    ).json()

    async with session_scope(org_id=org_id) as db:
        tool_row = await db.get(Tool, uuid.UUID(tool["id"]))
        with pytest.raises(AppError) as exc:
            await execute_connector_tool(db, tool=tool_row, args={}, org_id=org_id)

    assert exc.value.code == "tool.device_offline"
