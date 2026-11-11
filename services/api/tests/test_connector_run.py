"""End-to-end: agent -> connector tool -> device -> result -> answer."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import respx

from app.connector.hub import DeviceSession, hub
from tests.test_runs_basic import BASE, make_agent, sse_text, sse_tool_call


@respx.mock
async def test_agent_uses_desktop_connector(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    device = (
        await client.post("/v1/devices", headers=auth_headers, json={"name": "اکسل حسابداری"})
    ).json()

    tool = (
        await client.post(
            "/v1/tools",
            headers=auth_headers,
            json={
                "slug": f"demo.excel.{uuid.uuid4().hex[:6]}",
                "name_fa": "افزودن ردیف اکسل",
                "kind": "connector",
                "input_schema": {
                    "type": "object",
                    "properties": {"file": {"type": "string"}},
                    "required": ["file"],
                },
                "actions": [
                    {"op": "office.open", "app": "excel", "path": "{{input.file}}"},
                    {"op": "office.save"},
                ],
                "risk_level": "low",
                "approval_policy": "auto",
                "config": {"device_id": device["id"]},
            },
        )
    ).json()

    agent = await make_agent(client, auth_headers)
    await client.put(
        f"/v1/agents/{agent['id']}/tools",
        headers=auth_headers,
        json=[{"tool_id": tool["id"], "permission_level": "auto"}],
    )
    schemas = (
        await client.get(
            "/v1/tools/llm-schemas", params={"agent_id": agent["id"]}, headers=auth_headers
        )
    ).json()
    llm_name = next(row["name"] for row in schemas if row["slug"] == tool["slug"])

    async def send(payload: dict[str, Any]) -> None:
        hub.resolve(
            payload["call_id"],
            {"ok": True, "output": [{"step": 0, "opened": True}, {"step": 1, "saved": True}]},
        )

    hub.register(
        DeviceSession(
            device_id=uuid.UUID(device["id"]),
            org_id=org_id,
            send=send,
            manifest={"ops": ["office.open", "office.save"]},
        )
    )
    try:
        route = respx.post(f"{BASE}/chat/completions")
        route.mock(
            side_effect=[
                httpx.Response(
                    200,
                    text=sse_tool_call("call_x", llm_name, '{"file": "D:/data/sales.xlsx"}'),
                ),
                httpx.Response(200, text=sse_text("ردیف ثبت شد.")),
            ]
        )

        response = await client.post(
            f"/v1/agents/{agent['id']}/runs",
            headers=auth_headers,
            json={"input": "یک ردیف به فایل فروش اضافه کن", "stream": False},
        )
        body = response.json()
        assert body["run"]["status"] == "completed", body
        assert body["text"] == "ردیف ثبت شد."

        invocations = (
            await client.get(
                f"/v1/runs/{body['run']['id']}/invocations", headers=auth_headers
            )
        ).json()
        assert len(invocations) == 1
        assert invocations[0]["status"] == "ok"
        assert invocations[0]["result"]["device_id"] == device["id"]
        assert invocations[0]["result"]["steps"] == 2
    finally:
        hub.unregister(uuid.UUID(device["id"]))
