"""Cron worker: due tasks, single fire, run-now endpoint, task approval."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import respx
from sqlalchemy import update

from app.core.config import get_settings
from app.db.models import AgentTask, Run
from app.db.session import session_scope
from app.runtime.starter import prepare_task_run
from app.workers import scheduler

BASE = "https://api.sched.test/v1"
MODELS_PAYLOAD = {
    "object": "list",
    "data": [
        {
            "id": "sched-model",
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


async def make_agent(client: Any, headers: dict[str, str]) -> dict[str, Any]:
    provider = (
        await client.post(
            "/v1/providers",
            headers=headers,
            json={
                "name": f"sched-{uuid.uuid4().hex[:6]}",
                "kind": "openai_compatible",
                "base_url": BASE,
                "api_key": "sk-sched-key",
            },
        )
    ).json()
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))
    synced = await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=headers)
    assert synced.status_code == 200, synced.text
    priced = await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=headers)
    assert priced.status_code == 200, priced.text
    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=headers)
    ).json()
    assert models, f"no models synced: {synced.json()}"
    response = await client.post(
        "/v1/agents",
        headers=headers,
        json={"name": f"ایجنت زمان‌بند {uuid.uuid4().hex[:4]}", "model_id": models[0]["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_task(
    client: Any, headers: dict[str, str], agent_id: str, **overrides: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"وظیفه {uuid.uuid4().hex[:5]}",
        "prompt_template": "گزارش روزانه فروش را آماده کن.",
        "trigger_type": "manual",
    }
    payload.update(overrides)
    response = await client.post(f"/v1/agents/{agent_id}/tasks", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def only_active(task_id: uuid.UUID) -> None:
    """Deactivate every other scheduled task so a tick only sees ours."""
    async with session_scope(bypass_rls=True) as db:
        await db.execute(update(AgentTask).values(is_active=False))
        await db.execute(update(AgentTask).where(AgentTask.id == task_id).values(is_active=True))


async def get_run(org_id: uuid.UUID, run_id: uuid.UUID) -> Run:
    async with session_scope(org_id=org_id) as db:
        run = await db.get(Run, run_id)
        assert run is not None
        return run


async def wait_for_status(
    org_id: uuid.UUID, run_id: uuid.UUID, statuses: set[str], timeout: float = 20.0
) -> Run:
    deadline = time.monotonic() + timeout
    run = await get_run(org_id, run_id)
    while time.monotonic() < deadline:
        run = await get_run(org_id, run_id)
        if run.status in statuses:
            return run
        await asyncio.sleep(0.2)
    raise AssertionError(f"run {run_id} stayed in {run.status}")


@respx.mock
async def test_run_task_now_executes_with_trigger_task(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(client, auth_headers, agent["id"])
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("گزارش آماده است."))
    )

    response = await client.post(
        f"/v1/agents/{agent['id']}/tasks/{task['id']}/run", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run"]["trigger"] == "task"
    assert body["run"]["task_id"] == task["id"]
    assert body["run"]["status"] == "completed"
    assert body["text"] == "گزارش آماده است."

    tasks = (await client.get(f"/v1/agents/{agent['id']}/tasks", headers=auth_headers)).json()
    assert tasks[0]["last_run_at"] is not None
    assert tasks[0]["next_run_at"] is None  # manual task: no schedule


@respx.mock
async def test_tick_fires_once_and_runs_the_engine(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(
        client,
        auth_headers,
        agent["id"],
        trigger_type="schedule",
        schedule_cron="* * * * *",
    )
    await only_active(uuid.UUID(task["id"]))
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("اجرای زمان‌بندی‌شده"))
    )

    moment = datetime.now(UTC).replace(second=0, microsecond=0)
    started = await scheduler.tick(now=moment, settings=get_settings())
    assert len(started) == 1, started

    again = await scheduler.tick(now=moment, settings=get_settings())
    assert again == [], "the same minute must not fire twice"

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    run = await wait_for_status(org_id, started[0], {"completed", "failed"})
    assert run.status == "completed"
    assert run.trigger == "task"
    assert run.task_id == uuid.UUID(task["id"])
    assert run.cost_irr > 0


@respx.mock
async def test_inactive_task_is_not_scheduled(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(
        client,
        auth_headers,
        agent["id"],
        trigger_type="schedule",
        schedule_cron="* * * * *",
        is_active=False,
    )
    async with session_scope(bypass_rls=True) as db:
        await db.execute(update(AgentTask).values(is_active=False))

    started = await scheduler.tick(now=datetime.now(UTC), settings=get_settings())
    assert started == []
    async with session_scope(bypass_rls=True) as db:
        row = await db.get(AgentTask, uuid.UUID(task["id"]))
        assert row is not None and row.last_run_at is None


@respx.mock
async def test_due_tasks_requires_a_runnable_agent(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(
        client,
        auth_headers,
        agent["id"],
        trigger_type="schedule",
        schedule_cron="* * * * *",
    )
    await only_active(uuid.UUID(task["id"]))
    # detach the model: the scheduler must ignore the task instead of failing
    await client.patch(f"/v1/agents/{agent['id']}", headers=auth_headers, json={"model_id": None})

    started = await scheduler.tick(now=datetime.now(UTC), settings=get_settings())
    assert started == []


@respx.mock
async def test_prepare_skips_while_previous_run_is_active(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(client, auth_headers, agent["id"])
    settings = get_settings()

    first = await prepare_task_run(uuid.UUID(task["id"]), settings=settings, mark_last_run=False)
    assert first is not None and first.execute is True
    second = await prepare_task_run(uuid.UUID(task["id"]), settings=settings)
    assert second is None, "a queued run must block a second one"

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    async with session_scope(org_id=org_id) as db:
        run = await db.get(Run, first.run_id)
        assert run is not None and run.status == "queued"
        await db.delete(run)


@respx.mock
async def test_task_requiring_approval_parks_then_runs_after_approve(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(
        client,
        auth_headers,
        agent["id"],
        trigger_type="schedule",
        schedule_cron="* * * * *",
        requires_approval=True,
    )
    await only_active(uuid.UUID(task["id"]))
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_text("بعد از تأیید اجرا شد."))
    )

    moment = datetime.now(UTC).replace(second=0, microsecond=0)
    started = await scheduler.tick(now=moment, settings=get_settings())
    assert len(started) == 1

    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    await asyncio.sleep(0.3)
    parked = await get_run(org_id, started[0])
    assert parked.status == "waiting_approval"
    assert parked.state.get("awaiting") == "task"
    assert parked.state.get("task_input", "").startswith("گزارش روزانه")

    approved = await client.post(
        f"/v1/runs/{started[0]}/approve", headers=auth_headers, json={"stream": False}
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["run"]["status"] == "completed"
    assert body["text"] == "بعد از تأیید اجرا شد."


@respx.mock
async def test_next_run_is_exposed_for_scheduled_tasks(
    client: Any, auth_headers: dict[str, str]
) -> None:
    agent = await make_agent(client, auth_headers)
    task = await create_task(
        client,
        auth_headers,
        agent["id"],
        trigger_type="schedule",
        schedule_cron="0 8 * * *",
    )
    listed = (await client.get(f"/v1/agents/{agent['id']}/tasks", headers=auth_headers)).json()
    next_run = listed[0]["next_run_at"]
    assert next_run is not None
    parsed = datetime.fromisoformat(next_run)
    assert parsed > datetime.now(UTC) - timedelta(minutes=1)
    assert task["schedule_cron"] == "0 8 * * *"


async def test_advisory_lock_is_held_for_the_process_lifetime() -> None:
    """Regression: a GC'd lock connection silently released the single-runner lock."""
    import gc

    settings = get_settings()
    assert await scheduler._hold_lock(settings) is True
    lock_connection = scheduler._lock_connection
    assert lock_connection is not None

    # nothing may collect the connection away while the worker is alive
    gc.collect()
    assert scheduler._lock_connection is lock_connection

    # a second worker (different session on the same key) must lose
    assert await scheduler._hold_lock(settings) is False

    await scheduler._release_lock()
    assert scheduler._lock_connection is None

    # asyncpg terminates the session asynchronously, so the lock may need a moment
    for _ in range(20):
        if await scheduler._hold_lock(settings):
            break
        await asyncio.sleep(0.15)
    else:  # pragma: no cover - only on a real leak
        raise AssertionError("advisory lock was not released")
    await scheduler._release_lock()
