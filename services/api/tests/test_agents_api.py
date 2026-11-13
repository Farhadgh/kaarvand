"""Agent API: CRUD, effective prompt, tasks, tools, workflow."""

from __future__ import annotations

import uuid
from typing import Any


async def _create_agent(client: Any, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"ایجنت {uuid.uuid4().hex[:6]}",
        "role": "assistant",
        "system_prompt_key": "agent.system.default",
        "max_tokens": 512,
        "temperature": "0.2",
    }
    payload.update(overrides)
    response = await client.post("/v1/agents", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_agent_crud(client: Any, auth_headers: dict[str, str]) -> None:
    agent = await _create_agent(client, auth_headers)
    assert agent["system_prompt_key"] == "agent.system.default"
    assert agent["model_id"] is None
    assert agent["is_active"] is True

    listed = (await client.get("/v1/agents", headers=auth_headers)).json()
    assert any(item["id"] == agent["id"] for item in listed)

    patched = await client.patch(
        f"/v1/agents/{agent['id']}",
        headers=auth_headers,
        json={"name": "حسابدار ارشد", "system_prompt_key": "agent.system.accountant"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "حسابدار ارشد"

    deleted = await client.delete(f"/v1/agents/{agent['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/v1/agents/{agent['id']}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "agent.not_found"


async def test_unknown_prompt_key_is_rejected(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={"name": "بدون پرامپت", "system_prompt_key": "agent.system.nope"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "prompt.not_found"


async def test_effective_prompt_renders_role_persona(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await _create_agent(
        client, auth_headers, name="حسابدار ارشد", system_prompt_key="agent.system.accountant"
    )
    response = await client.get(f"/v1/agents/{agent['id']}/prompt", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "حسابدار ارشد" in body["rendered"]
    assert "سازمان نمونه" in body["rendered"]
    assert "{{" not in body["rendered"]
    assert body["missing"] == []
    assert any(character in "۰۱۲۳۴۵۶۷۸۹" for character in body["rendered"])


async def test_tasks_validation_and_cron(client: Any, auth_headers: dict[str, str]) -> None:
    agent = await _create_agent(client, auth_headers)
    base = f"/v1/agents/{agent['id']}/tasks"

    no_prompt = await client.post(base, json={"name": "بی‌پرامپت"}, headers=auth_headers)
    assert no_prompt.status_code == 422

    schedule_without_cron = await client.post(
        base,
        json={"name": "زمان‌بندی", "prompt_template": "x", "trigger_type": "schedule"},
        headers=auth_headers,
    )
    assert schedule_without_cron.status_code == 422

    bad_cron = await client.post(
        base,
        json={
            "name": "کرون غلط",
            "prompt_template": "x",
            "trigger_type": "schedule",
            "schedule_cron": "99 8 * * *",
        },
        headers=auth_headers,
    )
    assert bad_cron.status_code == 422

    created = await client.post(
        base,
        json={
            "name": "گزارش روزانه فروش",
            "prompt_key": "agent.task.daily_sales_report",
            "trigger_type": "schedule",
            "schedule_cron": "0 8 * * *",
            "requires_approval": True,
            "inputs_schema": {"type": "object", "properties": {"data": {"type": "string"}}},
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["schedule_cron"] == "0 8 * * *"
    assert task["requires_approval"] is True

    patched = await client.patch(
        f"{base}/{task['id']}", json={"is_active": False}, headers=auth_headers
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    deleted = await client.delete(f"{base}/{task['id']}", headers=auth_headers)
    assert deleted.status_code == 204


async def test_workflow_is_validated_and_versioned(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await _create_agent(client, auth_headers)
    url = f"/v1/agents/{agent['id']}/workflow"

    graph = {
        "nodes": [
            {"id": "s", "type": "start"},
            {"id": "ask", "type": "llm", "config": {"prompt_key": "agent.system.default"}},
            {"id": "approve", "type": "human_approval"},
            {"id": "e", "type": "end"},
        ],
        "edges": [
            {"from": "s", "to": "ask"},
            {"from": "ask", "to": "approve"},
            {"from": "approve", "to": "e"},
        ],
    }
    first = await client.put(url, json={"graph": graph}, headers=auth_headers)
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1
    assert first.json()["is_active"] is True

    second = await client.put(url, json={"graph": graph}, headers=auth_headers)
    assert second.json()["version"] == 2

    active = (await client.get(url, headers=auth_headers)).json()
    assert active["version"] == 2

    bad = await client.put(
        url,
        json={"graph": {"nodes": [{"id": "x", "type": "teleport"}], "edges": []}},
        headers=auth_headers,
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "workflow.invalid"


async def test_agent_tools_rejects_unknown_tool(client: Any, auth_headers: dict[str, str]) -> None:
    agent = await _create_agent(client, auth_headers)
    response = await client.put(
        f"/v1/agents/{agent['id']}/tools",
        json=[{"tool_id": str(uuid.uuid4()), "permission_level": "confirm"}],
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tool.not_found"


async def test_customer_can_create_agent(client: Any, viewer_headers: dict[str, str]) -> None:
    """Customers build their own agents; only platform data stays admin-only."""
    response = await client.post(
        "/v1/agents", json={"name": "ایجنت من"}, headers=viewer_headers
    )
    assert response.status_code == 201, response.text
