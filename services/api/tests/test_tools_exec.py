"""Tool execution service: policy gate, connector contract, audit trail."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import Tool, ToolInvocation
from app.db.session import session_scope
from app.tools.service import execute_tool


async def _create(client: Any, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slug": f"demo.exec.{uuid.uuid4().hex[:6]}",
        "name_fa": "ابزار اجرا",
        "kind": "http",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "config": {
            "method": "POST",
            "url": "https://api.demo.test/run",
            "allowed_domains": ["demo.test"],
            "body": {"text": "{{text}}"},
        },
        "risk_level": "low",
        "approval_policy": "auto",
    }
    payload.update(overrides)
    response = await client.post("/v1/tools", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_high_risk_needs_approval(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    created = await _create(client, auth_headers, risk_level="high")

    async with session_scope(org_id=org_id) as db:
        tool = await db.get(Tool, uuid.UUID(created["id"]))
        with pytest.raises(AppError) as exc:
            await execute_tool(db, tool=tool, args={"text": "x"}, org_id=org_id)

    assert exc.value.code == "tool.approval_required"
    assert exc.value.status_code == 409


async def test_deny_policy_blocks(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    created = await _create(client, auth_headers, approval_policy="deny")

    async with session_scope(org_id=org_id) as db:
        tool = await db.get(Tool, uuid.UUID(created["id"]))
        with pytest.raises(AppError) as exc:
            await execute_tool(db, tool=tool, args={"text": "x"}, org_id=org_id)

    assert exc.value.code == "tool.denied"


async def test_connector_without_device_is_audited(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    created = await _create(
        client,
        auth_headers,
        kind="connector",
        input_schema={"type": "object", "properties": {}},
        config={},
        actions=[{"op": "office.save"}],
    )

    async with session_scope(org_id=org_id) as db:
        tool = await db.get(Tool, uuid.UUID(created["id"]))
        with pytest.raises(AppError) as exc:
            await execute_tool(db, tool=tool, args={}, org_id=org_id, force=True)

    assert exc.value.code == "tool.device_offline"

    async with session_scope(org_id=org_id) as db:
        rows = (
            await db.execute(
                select(ToolInvocation).where(ToolInvocation.tool_slug == created["slug"])
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].result["error"] == "tool.device_offline"


async def test_builtin_now_jalali_via_service(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    tools = (await client.get("/v1/tools", headers=auth_headers)).json()
    builtin = next(row for row in tools if row["slug"] == "system.now_jalali")

    async with session_scope(org_id=org_id) as db:
        tool = await db.get(Tool, uuid.UUID(builtin["id"]))
        outcome = await execute_tool(db, tool=tool, args={}, org_id=org_id)

    result = outcome["result"]
    assert result["timezone"] == "Asia/Tehran"
    assert any(character in "۰۱۲۳۴۵۶۷۸۹" for character in result["jalali"])
    assert outcome["invocation_id"]
