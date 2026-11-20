"""Ownership: an agent, its runs and its ledger rows belong to one account.

The platform runs as a single tenant, so ``org_id`` alone would let every
customer read everyone else's work. These tests pin the per user rule:
customers only see what they created, the admin still sees the whole tenant.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

import httpx
import respx
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Run, UsageLedger, User
from app.db.session import session_scope

BASE = "https://api.ownership.test/v1"
MODELS_PAYLOAD = {
    "object": "list",
    "data": [
        {
            "id": "ownership-model",
            "context_length": 16000,
            "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        }
    ],
}


def _sse(text: str) -> str:
    events = [
        {"choices": [{"delta": {"content": text}}]},
        {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    ]
    body = "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)
    return body + "data: [DONE]\n\n"


async def _customer(
    client: Any, org_id: str, password: str = "customer-pass-123"
) -> dict[str, str]:
    """A password customer account of the same org, logged in."""
    email = f"cust-{uuid.uuid4().hex[:6]}@openbot.local"
    async with session_scope(bypass_rls=True) as db:
        db.add(
            User(
                org_id=uuid.UUID(org_id),
                email=email,
                full_name="مشتری",
                password_hash=hash_password(password),
                role="user",
            )
        )
    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _me(client: Any, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _agent_with_model(
    client: Any, *, admin: dict[str, str], customer: dict[str, str]
) -> dict[str, Any]:
    """Admin owns the provider/model; the customer owns the agent built on it."""
    provider = (
        await client.post(
            "/v1/providers",
            headers=admin,
            json={
                "name": f"ownership-{uuid.uuid4().hex[:6]}",
                "kind": "openai_compatible",
                "base_url": BASE,
                "api_key": "sk-ownership",
            },
        )
    ).json()
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))
    await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=admin)
    await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=admin)
    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=admin)
    ).json()

    created = await client.post(
        "/v1/agents",
        headers=customer,
        json={"name": f"ایجنت مشتری {uuid.uuid4().hex[:4]}", "model_id": models[0]["id"]},
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_customers_only_see_their_own_agents(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = admin_tokens["user"]["org_id"]
    first = await _customer(client, org_id)
    second = await _customer(client, org_id)

    created = await client.post(
        "/v1/agents",
        headers=first,
        json={"name": "ایجنت اول", "system_prompt_key": "agent.system.default"},
    )
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["created_by"] == (await _me(client, first))["id"]

    mine = (await client.get("/v1/agents", headers=first)).json()
    assert [row["id"] for row in mine] == [agent["id"]]
    assert (await client.get("/v1/agents", headers=second)).json() == []

    hidden = await client.get(f"/v1/agents/{agent['id']}", headers=second)
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "agent.not_found"
    # ... and it is also not editable, deletable or runnable
    assert (
        await client.patch(f"/v1/agents/{agent['id']}", headers=second, json={"name": "دزدیده"})
    ).status_code == 404
    assert (await client.delete(f"/v1/agents/{agent['id']}", headers=second)).status_code == 404
    assert (
        await client.post(
            f"/v1/agents/{agent['id']}/runs",
            headers=second,
            json={"input": "سلام", "stream": False},
        )
    ).status_code == 404

    # the platform admin still sees the whole tenant
    everything = (await client.get("/v1/agents", headers=auth_headers)).json()
    assert agent["id"] in [row["id"] for row in everything]


@respx.mock
async def test_run_and_ledger_are_attributed_to_the_customer(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = admin_tokens["user"]["org_id"]
    first = await _customer(client, org_id)
    second = await _customer(client, org_id)
    agent = await _agent_with_model(client, admin=auth_headers, customer=first)
    first_id = (await _me(client, first))["id"]

    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=_sse("سلام، من دستیار شما هستم."))
    )
    response = await client.post(
        f"/v1/agents/{agent['id']}/runs",
        headers=first,
        json={"input": "سلام", "stream": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run"]["status"] == "completed"
    assert body["run"]["created_by"] == first_id
    assert body["run"]["cost_usd"] is None  # customers never see the USD cost
    assert body["run"]["cost_irr"] > 0

    run_id = uuid.UUID(body["run"]["id"])
    async with session_scope(org_id=uuid.UUID(org_id)) as db:
        run = await db.get(Run, run_id)
        assert run is not None and str(run.created_by) == first_id
        ledger = (
            (await db.execute(select(UsageLedger).where(UsageLedger.run_id == run_id)))
            .scalars()
            .all()
        )
        assert len(ledger) == 1
        assert str(ledger[0].user_id) == first_id
        assert ledger[0].cost_irr == body["run"]["cost_irr"]
        assert Decimal(ledger[0].cost_usd) > 0

    # another customer neither lists nor reads it
    assert (await client.get("/v1/runs", headers=second)).json() == []
    assert (await client.get(f"/v1/runs/{run_id}", headers=second)).status_code == 404
    assert (await client.get(f"/v1/runs/{run_id}/invocations", headers=second)).status_code == 404

    # the owner and the admin can
    assert [row["id"] for row in (await client.get("/v1/runs", headers=first)).json()] == [
        str(run_id)
    ]
    assert (await client.get(f"/v1/runs/{run_id}", headers=auth_headers)).status_code == 200
    assert (await client.get("/v1/runs", headers=auth_headers)).status_code == 200
