"""Run endpoints: start an agent, stream SSE, approve and inspect.

The engine runs in its **own** database session: it commits while streaming
(approval state, ledger) and must not disturb the request session.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import get_agent, get_org
from app.core.config import Settings, get_settings
from app.core.deps import ADMIN_ROLE, get_current_user, get_db, require_member
from app.core.errors import AppError, NotFoundError
from app.db.models import Run, ToolInvocation, User
from app.db.session import session_scope, set_tenant
from app.runtime.engine import RunEngine
from app.runtime.events import SSE_HEADERS, encode, event
from app.schemas.runs import (
    RunApproveIn,
    RunOut,
    RunResultOut,
    RunStartIn,
    ToolInvocationOut,
)

router = APIRouter(tags=["runs"])
operator = require_member


async def _get_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> Run:
    run = (
        await db.execute(select(Run).where(Run.id == run_id, Run.org_id == user.org_id))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(code="run.not_found")
    return run


def run_out(run: Run, user: User) -> RunOut:
    """Customers see the Toman price they paid, never the platform's USD cost."""
    out = RunOut.model_validate(run)
    if user.role != ADMIN_ROLE:
        out.cost_usd = None
    return out


async def _collect(engine: RunEngine) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    text = ""
    async for item in engine.events():
        if len(events) < 400:
            events.append(item)
        if item["event"] == "run.completed":
            text = str(item["data"].get("text") or "")
    return events, text


def _sse(
    *,
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
    input_text: str = "",
    conversation_id: uuid.UUID | None = None,
    approved: bool = False,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    async def generator() -> AsyncIterator[str]:
        async with session_scope(org_id=org_id) as engine_db:
            run = await engine_db.get(Run, run_id)
            if run is None:
                yield encode(event("run.failed", {"code": "run.not_found"}))
                return
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
            async for item in engine.events():
                yield encode(item)

    return generator()


async def _run_to_completion(
    *,
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
    input_text: str = "",
    conversation_id: uuid.UUID | None = None,
    approved: bool = False,
    max_tokens: int | None = None,
    hide_usd: bool = False,
) -> RunResultOut:
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
        events, text = await _collect(engine)
        fresh = (await engine_db.execute(select(Run).where(Run.id == run_id))).scalar_one()
        result = RunOut.model_validate(fresh)
        if hide_usd:
            result.cost_usd = None
        return RunResultOut(run=result, text=text, events=events)


@router.post("/agents/{agent_id}/runs")
async def start_run(
    agent_id: uuid.UUID,
    payload: RunStartIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(operator),
    settings: Settings = Depends(get_settings),
) -> Any:
    agent = await get_agent(db, user, agent_id)
    org = await get_org(db, user)
    org_id = org.id
    user_id = user.id

    run = Run(
        org_id=org_id,
        agent_id=agent.id,
        conversation_id=payload.conversation_id,
        task_id=payload.task_id,
        status="queued",
        trigger="manual",
        state={},
    )
    db.add(run)
    await db.flush()
    run_id = run.id
    await db.commit()
    await set_tenant(db, org_id)

    if payload.stream:
        return StreamingResponse(
            _sse(
                org_id=org_id,
                run_id=run_id,
                user_id=user_id,
                settings=settings,
                input_text=payload.input,
                conversation_id=payload.conversation_id,
                max_tokens=payload.max_tokens,
            ),
            headers=SSE_HEADERS,
        )

    return await _run_to_completion(
        org_id=org_id,
        run_id=run_id,
        user_id=user_id,
        settings=settings,
        input_text=payload.input,
        conversation_id=payload.conversation_id,
        max_tokens=payload.max_tokens,
        hide_usd=user.role != ADMIN_ROLE,
    )


@router.post("/runs/{run_id}/approve")
async def approve_run(
    run_id: uuid.UUID,
    payload: RunApproveIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(operator),
    settings: Settings = Depends(get_settings),
) -> Any:
    run = await _get_run(db, user, run_id)
    if run.status != "waiting_approval":
        raise AppError(
            code="run.not_waiting_approval",
            status_code=409,
            params={"status": run.status},
        )

    org = await get_org(db, user)
    org_id = org.id
    user_id = user.id
    # a task parked for approval carries its instruction in the run state
    input_text = ""
    if isinstance(run.state, dict):
        input_text = str(run.state.get("task_input") or "")

    if payload.stream:
        return StreamingResponse(
            _sse(
                org_id=org_id,
                run_id=run_id,
                user_id=user_id,
                settings=settings,
                input_text=input_text,
                approved=True,
            ),
            headers=SSE_HEADERS,
        )

    return await _run_to_completion(
        org_id=org_id,
        run_id=run_id,
        user_id=user_id,
        settings=settings,
        input_text=input_text,
        approved=True,
        hide_usd=user.role != ADMIN_ROLE,
    )


@router.get("/runs", response_model=list[RunOut])
async def list_runs(
    agent_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RunOut]:
    stmt = select(Run).where(Run.org_id == user.org_id)
    if agent_id:
        stmt = stmt.where(Run.agent_id == agent_id)
    if status_filter:
        stmt = stmt.where(Run.status == status_filter)
    rows = (
        await db.execute(stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return [run_out(row, user) for row in rows]


@router.get("/runs/{run_id}", response_model=RunOut)
async def read_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RunOut:
    return run_out(await _get_run(db, user, run_id), user)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(operator),
) -> RunOut:
    run = await _get_run(db, user, run_id)
    if run.status in {"completed", "failed", "cancelled"}:
        return run_out(run, user)
    run.status = "cancelled"
    await db.flush()
    return run_out(run, user)


@router.get("/runs/{run_id}/invocations", response_model=list[ToolInvocationOut])
async def run_invocations(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ToolInvocationOut]:
    run = await _get_run(db, user, run_id)
    rows = (
        await db.execute(
            select(ToolInvocation)
            .where(ToolInvocation.run_id == run.id)
            .order_by(ToolInvocation.created_at)
        )
    ).scalars().all()
    return [ToolInvocationOut.model_validate(row) for row in rows]
