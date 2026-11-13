"""Prompt API: browse, version, publish, rollback, preview."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import get_agent, get_org
from app.core.deps import get_current_user, get_db, require_member
from app.core.errors import ForbiddenError
from app.db.models import Prompt, User
from app.prompts import service
from app.prompts.render import base_values, extract_variables, preview
from app.schemas.prompts import (
    PromptCreate,
    PromptOut,
    PromptPreviewIn,
    PromptPreviewOut,
    PromptUpdate,
    PromptVersionOut,
    RollbackIn,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])
editor = require_member


def _ensure_editable(prompt: Prompt) -> None:
    if prompt.org_id is None:
        raise ForbiddenError(code="prompt.global_readonly")


def _ensure_visible(prompt: Prompt, user: User) -> None:
    if prompt.org_id is not None and prompt.org_id != user.org_id:
        raise ForbiddenError(code="prompt.not_accessible")


@router.get("", response_model=list[PromptOut])
async def list_prompts(
    kind: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    locale: str = "fa",
    q: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PromptOut]:
    stmt = select(Prompt).where(
        or_(Prompt.org_id == user.org_id, Prompt.org_id.is_(None)), Prompt.locale == locale
    )
    if kind:
        stmt = stmt.where(Prompt.kind == kind)
    if status_filter:
        stmt = stmt.where(Prompt.status == status_filter)
    if q:
        stmt = stmt.where(Prompt.key.ilike(f"%{q}%") | Prompt.title_fa.ilike(f"%{q}%"))
    rows = (await db.execute(stmt.order_by(Prompt.org_id.is_(None), Prompt.key))).scalars().all()
    return [PromptOut.model_validate(row) for row in rows]


@router.post("", response_model=PromptOut, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    payload: PromptCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> PromptOut:
    prompt = await service.create_prompt(
        db,
        org_id=user.org_id,
        key=payload.key,
        title_fa=payload.title_fa,
        template=payload.template,
        kind=payload.kind,
        locale=payload.locale,
        variables=payload.variables,
        status="published" if payload.publish else "draft",
        user_id=user.id,
    )
    return PromptOut.model_validate(prompt)


@router.get("/resolve/{key}", response_model=PromptPreviewOut)
async def resolve_effective_prompt(
    key: str,
    agent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromptPreviewOut:
    org = await get_org(db, user)
    agent = await get_agent(db, user, agent_id) if agent_id else None
    prompt = await service.resolve_prompt(db, org_id=user.org_id, key=key, require_published=False)
    values = base_values(
        org_name=org.name,
        org_timezone=org.timezone,
        agent_name=agent.name if agent else None,
        agent_role=agent.role if agent else None,
        digits=org.digits,
    )
    result = preview(prompt.template, values)
    return PromptPreviewOut(
        key=prompt.key,
        version=prompt.current_version,
        template=prompt.template,
        rendered=result["rendered"],
        variables=result["variables"],
        missing=result["missing"],
    )


@router.get("/{prompt_id}", response_model=PromptOut)
async def read_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromptOut:
    prompt = await service.get_prompt(db, prompt_id)
    _ensure_visible(prompt, user)
    return PromptOut.model_validate(prompt)


@router.put("/{prompt_id}", response_model=PromptOut)
async def update_prompt(
    prompt_id: uuid.UUID,
    payload: PromptUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> PromptOut:
    prompt = await service.get_prompt(db, prompt_id)
    _ensure_editable(prompt)
    await service.update_prompt(
        db,
        prompt,
        template=payload.template,
        title_fa=payload.title_fa,
        variables=payload.variables,
        note=payload.note,
        publish_now=payload.publish,
        user_id=user.id,
    )
    return PromptOut.model_validate(prompt)


@router.post("/{prompt_id}/publish", response_model=PromptOut)
async def publish_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> PromptOut:
    prompt = await service.get_prompt(db, prompt_id)
    _ensure_editable(prompt)
    await service.publish_prompt(db, prompt)
    return PromptOut.model_validate(prompt)


@router.post("/{prompt_id}/rollback", response_model=PromptOut)
async def rollback_prompt(
    prompt_id: uuid.UUID,
    payload: RollbackIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> PromptOut:
    prompt = await service.get_prompt(db, prompt_id)
    _ensure_editable(prompt)
    await service.rollback_prompt(db, prompt, version=payload.version, user_id=user.id)
    return PromptOut.model_validate(prompt)


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionOut])
async def prompt_versions(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PromptVersionOut]:
    prompt = await service.get_prompt(db, prompt_id)
    _ensure_visible(prompt, user)
    rows = await service.list_versions(db, prompt.id)
    return [PromptVersionOut.model_validate(row) for row in rows]


@router.post("/{prompt_id}/preview", response_model=PromptPreviewOut)
async def preview_prompt(
    prompt_id: uuid.UUID,
    payload: PromptPreviewIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromptPreviewOut:
    prompt = await service.get_prompt(db, prompt_id)
    _ensure_visible(prompt, user)

    org = await get_org(db, user)
    agent = await get_agent(db, user, payload.agent_id) if payload.agent_id else None
    values: dict[str, Any] = base_values(
        org_name=org.name,
        org_timezone=org.timezone,
        agent_name=agent.name if agent else None,
        agent_role=agent.role if agent else None,
        digits=org.digits,
        extra=payload.values,
    )
    result = preview(prompt.template, values)
    return PromptPreviewOut(
        key=prompt.key,
        version=prompt.current_version,
        template=prompt.template,
        rendered=result["rendered"],
        variables=extract_variables(prompt.template),
        missing=result["missing"],
    )
