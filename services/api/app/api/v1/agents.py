"""Agent API: CRUD, effective prompt, tasks, tool bindings, workflow."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import effective_prompt, get_agent, validate_model
from app.agents.workflow import validate_graph
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db, require_member
from app.core.errors import AppError, NotFoundError
from app.db.models import Agent, AgentTask, AgentTool, AgentWorkflow, Model, Tool, User
from app.prompts.service import resolve_prompt
from app.runtime.cron import next_run_utc
from app.runtime.starter import prepare_task_run, run_to_result
from app.schemas.agents import (
    AgentCreate,
    AgentOut,
    AgentTaskCreate,
    AgentTaskOut,
    AgentTaskUpdate,
    AgentToolIn,
    AgentToolOut,
    AgentUpdate,
    WorkflowIn,
    WorkflowOut,
)
from app.schemas.prompts import PromptPreviewOut
from app.schemas.runs import RunResultOut

router = APIRouter(prefix="/agents", tags=["agents"])
editor = require_member
runner = require_member


def task_out(task: AgentTask) -> AgentTaskOut:
    out = AgentTaskOut.model_validate(task)
    if task.trigger_type == "schedule" and task.is_active and task.schedule_cron:
        out.next_run_at = next_run_utc(task.schedule_cron)
    return out


async def _model_of(db: AsyncSession, agent: Agent) -> Model | None:
    return await db.get(Model, agent.model_id) if agent.model_id else None


async def to_out(db: AsyncSession, agent: Agent) -> AgentOut:
    out = AgentOut.model_validate(agent)
    model = await _model_of(db, agent)
    if model is not None:
        out.model_external_id = model.external_id
        out.model_display_name_fa = model.display_name_fa
    return out


async def _ensure_prompt_key(db: AsyncSession, user: User, key: str) -> None:
    await resolve_prompt(db, org_id=user.org_id, key=key, require_published=False)


@router.get("", response_model=list[AgentOut])
async def list_agents(
    is_active: bool | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentOut]:
    stmt = select(Agent).where(Agent.org_id == user.org_id)
    if is_active is not None:
        stmt = stmt.where(Agent.is_active.is_(is_active))
    if q:
        stmt = stmt.where(Agent.name.ilike(f"%{q}%") | Agent.role.ilike(f"%{q}%"))
    agents = (
        (await db.execute(stmt.order_by(Agent.created_at).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return [await to_out(db, agent) for agent in agents]


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> AgentOut:
    await _ensure_prompt_key(db, user, payload.system_prompt_key)
    if payload.model_id:
        await validate_model(db, user, payload.model_id)

    agent = Agent(
        org_id=user.org_id,
        name=payload.name,
        role=payload.role,
        avatar_url=payload.avatar_url,
        system_prompt_key=payload.system_prompt_key,
        model_id=payload.model_id,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        memory_mode=payload.memory_mode,
        guardrails=payload.guardrails,
        monthly_budget_irr=payload.monthly_budget_irr,
        is_active=payload.is_active,
        created_by=user.id,
    )
    db.add(agent)
    await db.flush()
    return await to_out(db, agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def read_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    return await to_out(db, await get_agent(db, user, agent_id))


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> AgentOut:
    agent = await get_agent(db, user, agent_id)
    data: dict[str, Any] = payload.model_dump(exclude_unset=True)

    if "system_prompt_key" in data and data["system_prompt_key"]:
        await _ensure_prompt_key(db, user, data["system_prompt_key"])
    if data.get("model_id"):
        await validate_model(db, user, data["model_id"])

    for key, value in data.items():
        setattr(agent, key, value)
    await db.flush()
    return await to_out(db, agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    agent = await get_agent(db, user, agent_id)
    await db.delete(agent)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{agent_id}/prompt", response_model=PromptPreviewOut)
async def agent_prompt(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromptPreviewOut:
    agent = await get_agent(db, user, agent_id)
    result = await effective_prompt(db, user=user, agent=agent)
    return PromptPreviewOut(**result)


async def _get_task(db: AsyncSession, agent: Agent, task_id: uuid.UUID) -> AgentTask:
    task = (
        await db.execute(
            select(AgentTask).where(AgentTask.id == task_id, AgentTask.agent_id == agent.id)
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(code="task.not_found")
    return task


@router.get("/{agent_id}/tasks", response_model=list[AgentTaskOut])
async def list_tasks(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentTaskOut]:
    agent = await get_agent(db, user, agent_id)
    rows = (
        (
            await db.execute(
                select(AgentTask)
                .where(AgentTask.agent_id == agent.id)
                .order_by(AgentTask.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [task_out(row) for row in rows]


@router.post("/{agent_id}/tasks", response_model=AgentTaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    agent_id: uuid.UUID,
    payload: AgentTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> AgentTaskOut:
    agent = await get_agent(db, user, agent_id)
    if payload.prompt_key:
        await _ensure_prompt_key(db, user, payload.prompt_key)

    task = AgentTask(
        agent_id=agent.id,
        name=payload.name,
        prompt_key=payload.prompt_key,
        prompt_template=payload.prompt_template,
        inputs_schema=payload.inputs_schema,
        steps=payload.steps,
        schedule_cron=payload.schedule_cron,
        trigger_type=payload.trigger_type,
        requires_approval=payload.requires_approval,
        is_active=payload.is_active,
    )
    db.add(task)
    await db.flush()
    return task_out(task)


@router.post("/{agent_id}/tasks/{task_id}/run", response_model=RunResultOut)
async def run_task_now(
    agent_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(runner),
    settings: Settings = Depends(get_settings),
) -> RunResultOut:
    """Execute a task immediately (same engine as the cron worker)."""
    agent = await get_agent(db, user, agent_id)
    task = await _get_task(db, agent, task_id)
    await db.commit()

    plan = await prepare_task_run(
        task.id, settings=settings, mark_last_run=True, user_id=user.id
    )
    if plan is None:
        raise AppError(
            code="task.not_runnable",
            status_code=409,
            params={"task": task.name},
        )
    if not plan.execute:
        raise AppError(
            code="task.approval_required",
            status_code=409,
            params={"run_id": str(plan.run_id)},
        )
    return await run_to_result(
        org_id=plan.org_id,
        run_id=plan.run_id,
        user_id=plan.user_id,
        settings=settings,
        input_text=plan.input_text,
    )


@router.patch("/{agent_id}/tasks/{task_id}", response_model=AgentTaskOut)
async def update_task(
    agent_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: AgentTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> AgentTaskOut:
    agent = await get_agent(db, user, agent_id)
    task = await _get_task(db, agent, task_id)
    data: dict[str, Any] = payload.model_dump(exclude_unset=True)

    if data.get("prompt_key"):
        await _ensure_prompt_key(db, user, data["prompt_key"])
    for key, value in data.items():
        setattr(task, key, value)

    if task.trigger_type == "schedule" and not task.schedule_cron:
        raise AppError(code="task.schedule_required", status_code=422)
    if not task.prompt_key and not task.prompt_template:
        raise AppError(code="task.prompt_required", status_code=422)

    await db.flush()
    return AgentTaskOut.model_validate(task)


@router.delete("/{agent_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    agent_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    agent = await get_agent(db, user, agent_id)
    task = await _get_task(db, agent, task_id)
    await db.delete(task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{agent_id}/tools", response_model=list[AgentToolOut])
async def list_agent_tools(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentToolOut]:
    agent = await get_agent(db, user, agent_id)
    rows = (
        (await db.execute(select(AgentTool).where(AgentTool.agent_id == agent.id))).scalars().all()
    )
    return [AgentToolOut.model_validate(row) for row in rows]


@router.put("/{agent_id}/tools", response_model=list[AgentToolOut])
async def set_agent_tools(
    agent_id: uuid.UUID,
    payload: list[AgentToolIn],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> list[AgentToolOut]:
    agent = await get_agent(db, user, agent_id)
    # dedupe by tool_id (last entry wins) so a repeated id cannot violate the
    # unique (agent_id, tool_id) constraint
    unique: dict[uuid.UUID, AgentToolIn] = {item.tool_id: item for item in payload}
    items = list(unique.values())
    wanted = set(unique)

    if wanted:
        available = set(
            (
                await db.execute(
                    select(Tool.id).where(
                        Tool.id.in_(wanted),
                        or_(Tool.org_id == user.org_id, Tool.org_id.is_(None)),
                    )
                )
            ).scalars()
        )
        missing = wanted - available
        if missing:
            raise AppError(
                code="tool.not_found",
                status_code=422,
                params={"tool_ids": [str(item) for item in missing]},
            )

    await db.execute(delete(AgentTool).where(AgentTool.agent_id == agent.id))
    for item in items:
        db.add(
            AgentTool(
                agent_id=agent.id,
                tool_id=item.tool_id,
                config=item.config,
                permission_level=item.permission_level,
                is_enabled=item.is_enabled,
            )
        )
    await db.flush()

    rows = (
        (await db.execute(select(AgentTool).where(AgentTool.agent_id == agent.id))).scalars().all()
    )
    return [AgentToolOut.model_validate(row) for row in rows]


@router.get("/{agent_id}/workflow", response_model=WorkflowOut | None)
async def read_workflow(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkflowOut | None:
    agent = await get_agent(db, user, agent_id)
    workflow = (
        await db.execute(
            select(AgentWorkflow)
            .where(AgentWorkflow.agent_id == agent.id, AgentWorkflow.is_active.is_(True))
            .order_by(AgentWorkflow.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return WorkflowOut.model_validate(workflow) if workflow else None


@router.put("/{agent_id}/workflow", response_model=WorkflowOut)
async def set_workflow(
    agent_id: uuid.UUID,
    payload: WorkflowIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> WorkflowOut:
    agent = await get_agent(db, user, agent_id)
    graph = validate_graph(payload.graph)

    last_version = (
        await db.execute(
            select(AgentWorkflow.version)
            .where(AgentWorkflow.agent_id == agent.id)
            .order_by(AgentWorkflow.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none() or 0

    if payload.activate:
        await db.execute(
            AgentWorkflow.__table__.update()  # noqa: SLF001 - bulk deactivate
            .where(AgentWorkflow.agent_id == agent.id)
            .values(is_active=False)
        )

    workflow = AgentWorkflow(
        agent_id=agent.id,
        version=last_version + 1,
        graph=graph,
        is_active=payload.activate,
    )
    db.add(workflow)
    await db.flush()
    return WorkflowOut.model_validate(workflow)
