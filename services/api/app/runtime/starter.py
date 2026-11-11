"""Shared helpers to start a run and drive it to completion.

Used by the HTTP endpoints (runs.py) and by the cron worker, so a scheduled run
behaves exactly like a manual one (same engine, same ledger, same approvals).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.models import Agent, AgentTask, Run, User
from app.db.session import session_scope
from app.prompts.render import base_values, render
from app.prompts.service import resolve_prompt
from app.runtime.engine import RunEngine
from app.schemas.runs import RunOut, RunResultOut

ACTIVE_STATUSES = ("queued", "running", "waiting_approval")


async def create_run(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    trigger: str = "manual",
    task_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
) -> Run:
    """Persist a queued run (the caller owns the transaction)."""
    run = Run(
        org_id=org_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        task_id=task_id,
        status="queued",
        trigger=trigger,
        state={},
    )
    db.add(run)
    await db.flush()
    return run


async def collect(engine: RunEngine) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    text = ""
    async for item in engine.events():
        if len(events) < 400:
            events.append(item)
        if item["event"] == "run.completed":
            text = str(item["data"].get("text") or "")
    return events, text


async def run_to_result(
    *,
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
    input_text: str = "",
    conversation_id: uuid.UUID | None = None,
    approved: bool = False,
    max_tokens: int | None = None,
) -> RunResultOut:
    """Run the engine in its own session (it commits while streaming)."""
    async with session_scope(org_id=org_id) as engine_db:
        run = await engine_db.get(Run, run_id)
        if run is None:
            raise NotFoundError(code="run.not_found")
        engine = RunEngine(
            engine_db,
            run=run,
            user_id=user_id,
            settings=settings,
            input_text=input_text,
            conversation_id=conversation_id,
            approved=approved,
            max_tokens=max_tokens,
        )
        events, text = await collect(engine)
        fresh = (await engine_db.execute(select(Run).where(Run.id == run_id))).scalar_one()
        return RunResultOut(run=RunOut.model_validate(fresh), text=text, events=events)


@dataclass(frozen=True)
class TaskRunPlan:
    """Everything needed to execute a task run after the row is committed."""

    run_id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    input_text: str
    execute: bool = True


async def prepare_task_run(
    task_id: uuid.UUID,
    *,
    settings: Settings,
    mark_last_run: bool = True,
    user_id: uuid.UUID | None = None,
) -> TaskRunPlan | None:
    """Create the run row for a task, or ``None`` when nothing should run.

    Skips when the agent is not runnable, when a previous run of the same task
    is still active, or when the task prompt cannot be resolved. When the task
    requires approval the run is parked in ``waiting_approval`` and the caller
    must **not** execute it (a human has to approve it first).
    """
    async with session_scope(bypass_rls=True, settings=settings) as db:
        task = await db.get(AgentTask, task_id)
        if task is None:
            return None
        agent = await db.get(Agent, task.agent_id)
        if agent is None or not agent.is_active or not agent.model_id:
            return None
        org_id = agent.org_id

        active = (
            await db.execute(
                select(Run.id)
                .where(Run.task_id == task_id, Run.status.in_(ACTIVE_STATUSES))
                .limit(1)
            )
        ).first()
        if active is not None:
            return None

        owner = user_id
        if owner is None:
            owner = (
                await db.execute(
                    select(User.id)
                    .where(User.org_id == org_id, User.is_active.is_(True))
                    .order_by((User.role != "owner"), User.created_at)
                    .limit(1)
                )
            ).scalar_one_or_none()
        if owner is None:
            return None

    async with session_scope(org_id=org_id, settings=settings) as db:
        task = await db.get(AgentTask, task_id)
        if task is None:
            return None
        try:
            input_text = await task_input_text(db, org_id=org_id, task=task)
        except Exception:  # a broken prompt must never crash the caller
            return None
        gated = bool(task.requires_approval)
        run = await create_run(
            db,
            org_id=org_id,
            agent_id=task.agent_id,
            trigger="task",
            task_id=task.id,
        )
        if gated:
            run.status = "waiting_approval"
            run.state = {"awaiting": "task", "task_input": input_text}
        run_id = run.id
        if mark_last_run:
            task.last_run_at = datetime.now(UTC)
        await db.flush()
    return TaskRunPlan(
        run_id=run_id,
        org_id=org_id,
        user_id=owner,
        input_text=input_text,
        execute=not gated,
    )


async def task_input_text(db: AsyncSession, *, org_id: uuid.UUID, task: AgentTask) -> str:
    """The instruction a task sends to the agent: its prompt, rendered."""
    template = task.prompt_template
    if task.prompt_key:
        prompt = await resolve_prompt(db, org_id=org_id, key=task.prompt_key)
        template = prompt.template
    if not template:
        return task.name
    values = base_values(extra={"task.name": task.name})
    return render(template, values, strict=False).strip() or task.name
