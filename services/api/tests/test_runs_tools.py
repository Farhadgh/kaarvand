"""Tool-calling loop and human approval inside a run."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import respx

from tests.test_runs_basic import BASE, make_agent, sse_text, sse_tool_call


@respx.mock
async def test_run_calls_bound_tool_then_answers(client: Any, auth_headers: dict[str, str]) -> None:
    tools = (await client.get("/v1/tools", headers=auth_headers)).json()
    builtin = next(row for row in tools if row["slug"] == "system.now_jalali")

    agent = await make_agent(client, auth_headers)
    bind = await client.put(
        f"/v1/agents/{agent['id']}/tools",
        headers=auth_headers,
        json=[{"tool_id": builtin["id"], "permission_level": "auto"}],
    )
    assert bind.status_code == 200, bind.text

    route = respx.post(f"{BASE}/chat/completions")
    route.mock(
        side_effect=[
            httpx.Response(200, text=sse_tool_call("call_1", "system_now_jalali", "{}")),
            httpx.Response(200, text=sse_text("امروز ۱۸ آبان ۱۴۰۵ است.")),
        ]
    )

    response = await client.post(
        f"/v1/agents/{agent['id']}/runs",
        headers=auth_headers,
        json={"input": "امروز چندم است؟", "stream": False},
    )
    body = response.json()
    assert body["run"]["status"] == "completed", body
    assert body["run"]["steps_taken"] == 2
    assert body["text"] == "امروز ۱۸ آبان ۱۴۰۵ است."

    names = [item["event"] for item in body["events"]]
    assert "tool.call" in names
    assert "tool.result" in names

    invocations = (
        await client.get(f"/v1/runs/{body['run']['id']}/invocations", headers=auth_headers)
    ).json()
    assert len(invocations) == 1
    assert invocations[0]["tool_slug"] == "system.now_jalali"
    assert invocations[0]["status"] == "ok"


@respx.mock
async def test_connector_tool_waits_for_approval_then_resumes(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)

    tool = (
        await client.post(
            "/v1/tools",
            headers=auth_headers,
            json={
                "slug": f"demo.device.{uuid.uuid4().hex[:6]}",
                "name_fa": "ابزار دستگاه",
                "kind": "connector",
                "input_schema": {"type": "object", "properties": {}},
                "actions": [{"op": "screenshot"}],
                "risk_level": "medium",
                "approval_policy": "confirm",
            },
        )
    ).json()
    await client.put(
        f"/v1/agents/{agent['id']}/tools",
        headers=auth_headers,
        json=[{"tool_id": tool["id"], "permission_level": "confirm"}],
    )

    schemas = (
        await client.get(
            "/v1/tools/llm-schemas",
            params={"agent_id": agent["id"]},
            headers=auth_headers,
        )
    ).json()
    llm_tool_name = next(row["name"] for row in schemas if row["slug"] == tool["slug"])

    route = respx.post(f"{BASE}/chat/completions")
    route.mock(
        side_effect=[
            httpx.Response(200, text=sse_tool_call("call_a", llm_tool_name, "{}")),
            httpx.Response(200, text=sse_text("انجام شد.")),
        ]
    )

    first = await client.post(
        f"/v1/agents/{agent['id']}/runs",
        headers=auth_headers,
        json={"input": "یک اسکرین‌شات بگیر", "stream": False},
    )
    body = first.json()
    run_id = body["run"]["id"]

    assert body["run"]["status"] == "waiting_approval", body
    assert any(item["event"] == "approval.required" for item in body["events"])
    assert body["run"]["steps_taken"] == 1

    approved = await client.post(
        f"/v1/runs/{run_id}/approve", headers=auth_headers, json={"stream": False}
    )
    approval_body = approved.json()
    assert approval_body["run"]["status"] == "completed", approval_body
    assert approval_body["text"] == "انجام شد."
    assert approval_body["run"]["steps_taken"] == 2

    invocations = (await client.get(f"/v1/runs/{run_id}/invocations", headers=auth_headers)).json()
    assert len(invocations) == 1
    # approved, but no desktop connector is connected in this test
    assert invocations[0]["status"] == "error"
    assert invocations[0]["result"]["error"] == "tool.device_offline"
    assert invocations[0]["approved_by"] is not None


async def test_approve_requires_waiting_run(client: Any, auth_headers: dict[str, str]) -> None:
    runs = (await client.get("/v1/runs", headers=auth_headers)).json()
    completed = next((row for row in runs if row["status"] == "completed"), None)
    if completed is None:
        return
    response = await client.post(
        f"/v1/runs/{completed['id']}/approve", headers=auth_headers, json={"stream": False}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "run.not_waiting_approval"
