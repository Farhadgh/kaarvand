"""Run engine basics: SSE streaming, usage ledger, Toman cost, budget guard."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

import httpx
import respx
from sqlalchemy import select

from app.db.models import UsageLedger
from app.db.session import session_scope

BASE = "https://api.run.test/v1"
MODELS_PAYLOAD = {
    "object": "list",
    "data": [
        {
            "id": "runner-model",
            "context_length": 32000,
            "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        }
    ],
}


def sse_text(text: str, tokens_in: int = 10, tokens_out: int = 5) -> str:
    events = [
        {"choices": [{"delta": {"content": text}}]},
        {"usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out}},
    ]
    body = "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)
    return body + "data: [DONE]\n\n"


def sse_tool_call(call_id: str, name: str, arguments: str) -> str:
    delta = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": call_id,
                            "function": {"name": name, "arguments": arguments},
                        }
                    ]
                }
            }
        ]
    }
    body = f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"
    body += f"data: {json.dumps({'usage': {'prompt_tokens': 8, 'completion_tokens': 4}})}\n\n"
    return body + "data: [DONE]\n\n"


async def make_agent(
    client: Any, headers: dict[str, str], *, budget: int | None = None
) -> dict[str, Any]:
    provider = (
        await client.post(
            "/v1/providers",
            headers=headers,
            json={
                "name": f"runner-{uuid.uuid4().hex[:6]}",
                "kind": "openai_compatible",
                "base_url": BASE,
                "api_key": "sk-runner-key",
            },
        )
    ).json()
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))
    await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=headers)
    await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=headers)

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=headers)
    ).json()
    response = await client.post(
        "/v1/agents",
        headers=headers,
        json={
            "name": f"ایجنت اجرا {uuid.uuid4().hex[:4]}",
            "model_id": models[0]["id"],
            "monthly_budget_irr": budget,
            "memory_mode": "short",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@respx.mock
async def test_run_completes_and_charges_in_toman(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent = await make_agent(client, auth_headers)
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("سلام، من دستیار شما هستم."))
    )

    response = await client.post(
        f"/v1/agents/{agent['id']}/runs",
        headers=auth_headers,
        json={"input": "سلام", "stream": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["run"]["status"] == "completed"
    assert body["text"] == "سلام، من دستیار شما هستم."
    assert body["run"]["tokens_in"] == 10
    assert body["run"]["tokens_out"] == 5
    assert body["run"]["steps_taken"] == 1
    assert Decimal(body["run"]["cost_usd"]) > 0
    assert body["run"]["cost_irr"] > 0
    assert Decimal(body["run"]["fx_rate"]) == Decimal("1000000")

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    async with session_scope(org_id=org_id) as db:
        rows = (
            (
                await db.execute(
                    select(UsageLedger).where(UsageLedger.run_id == uuid.UUID(body["run"]["id"]))
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].billable is False
    assert rows[0].cost_irr == body["run"]["cost_irr"]


@respx.mock
async def test_stream_mode_emits_sse_events(client: Any, auth_headers: dict[str, str]) -> None:
    agent = await make_agent(client, auth_headers)
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("پاسخ استریم"))
    )

    url = f"/v1/agents/{agent['id']}/runs"
    async with client.stream("POST", url, headers=auth_headers, json={"input": "سلام"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        collected: list[dict[str, Any]] = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                collected.append(json.loads(line[6:]))

    names = [item["event"] for item in collected]
    assert names[0] == "run.started"
    assert "token" in names
    assert names[-1] == "run.completed"
    joined = "".join(item["data"]["text"] for item in collected if item["event"] == "token")
    assert joined == "پاسخ استریم"


@respx.mock
async def test_agent_budget_blocks_the_run(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent = await make_agent(client, auth_headers, budget=1)
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])

    async with session_scope(org_id=org_id) as db:
        db.add(
            UsageLedger(
                org_id=org_id,
                agent_id=uuid.UUID(agent["id"]),
                tokens_in=100,
                tokens_out=100,
                cost_usd=Decimal("0.001"),
                markup_percent=Decimal("0"),
                fx_rate=Decimal("1000000"),
                cost_irr=1000,
                billable=False,
            )
        )

    response = await client.post(
        f"/v1/agents/{agent['id']}/runs",
        headers=auth_headers,
        json={"input": "سلام", "stream": False},
    )
    body = response.json()
    assert body["run"]["status"] == "failed"
    assert body["run"]["error_code"] == "budget.agent_exceeded"


async def test_viewer_cannot_start_run(client: Any, viewer_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/agents/00000000-0000-0000-0000-000000000000/runs",
        headers=viewer_headers,
        json={"input": "سلام", "stream": False},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.insufficient_role"


async def test_runs_list(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/runs", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
