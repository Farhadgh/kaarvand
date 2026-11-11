"""Agent helpers: model/prompt validation and effective prompt rendering."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import Agent, Model, Organization, Provider, User
from app.prompts.render import base_values, render
from app.prompts.service import resolve_prompt


async def get_org(db: AsyncSession, user: User) -> Organization:
    org = await db.get(Organization, user.org_id)
    if org is None:
        raise AppError(code="org.not_found", status_code=404)
    return org


async def validate_model(db: AsyncSession, user: User, model_id: uuid.UUID) -> Model:
    model = (
        await db.execute(
            select(Model)
            .join(Provider, Provider.id == Model.provider_id)
            .where(Model.id == model_id, Provider.org_id == user.org_id)
        )
    ).scalar_one_or_none()
    if model is None:
        raise AppError(code="model.not_found", status_code=422, params={"model_id": str(model_id)})
    if not model.is_enabled:
        raise AppError(code="model.disabled", status_code=422, params={"model_id": str(model_id)})
    return model


async def get_agent(db: AsyncSession, user: User, agent_id: uuid.UUID) -> Agent:
    agent = (
        await db.execute(select(Agent).where(Agent.id == agent_id, Agent.org_id == user.org_id))
    ).scalar_one_or_none()
    if agent is None:
        raise AppError(code="agent.not_found", status_code=404)
    return agent


async def effective_prompt(
    db: AsyncSession,
    *,
    user: User,
    agent: Agent,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    org = await get_org(db, user)
    prompt = await resolve_prompt(
        db, org_id=user.org_id, key=agent.system_prompt_key, require_published=False
    )
    values = base_values(
        org_name=org.name,
        org_timezone=org.timezone,
        agent_name=agent.name,
        agent_role=agent.role,
        digits=org.digits,
        extra=extra,
    )
    rendered = render(prompt.template, values, strict=False)
    return {
        "key": prompt.key,
        "version": prompt.current_version,
        "template": prompt.template,
        "rendered": rendered,
        "variables": list(prompt.variables or []),
        "missing": [name for name in (prompt.variables or []) if name not in values],
    }


def agent_out_payload(agent: Agent, model: Model | None) -> dict[str, Any]:
    return {
        "model_external_id": model.external_id if model else None,
        "model_display_name_fa": model.display_name_fa if model else None,
    }
