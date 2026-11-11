"""Prompt storage service: resolution, versioning, publish, rollback."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db.models import Prompt, PromptVersion
from app.prompts.render import extract_variables


async def resolve_prompt(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    key: str,
    locale: str = "fa",
    require_published: bool = True,
) -> Prompt:
    """Tenant override wins over the global prompt."""
    stmt = select(Prompt).where(
        Prompt.key == key,
        Prompt.locale == locale,
        or_(Prompt.org_id == org_id, Prompt.org_id.is_(None)),
    )
    if require_published:
        stmt = stmt.where(Prompt.status == "published")
    stmt = stmt.order_by(Prompt.org_id.is_(None)).limit(1)

    prompt = (await db.execute(stmt)).scalar_one_or_none()
    if prompt is None:
        raise NotFoundError(code="prompt.not_found", params={"key": key, "locale": locale})
    return prompt


async def get_prompt(db: AsyncSession, prompt_id: uuid.UUID) -> Prompt:
    prompt = await db.get(Prompt, prompt_id)
    if prompt is None:
        raise NotFoundError(code="prompt.not_found")
    return prompt


async def _ensure_unique(db: AsyncSession, org_id: uuid.UUID, key: str, locale: str) -> None:
    found = (
        await db.execute(
            select(Prompt.id).where(
                Prompt.org_id == org_id, Prompt.key == key, Prompt.locale == locale
            )
        )
    ).first()
    if found is not None:
        raise ConflictError(code="prompt.duplicate_key", params={"key": key})


async def create_prompt(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    key: str,
    title_fa: str,
    template: str,
    kind: str = "agent.system",
    locale: str = "fa",
    variables: list[str] | None = None,
    status: str = "draft",
    user_id: uuid.UUID | None = None,
) -> Prompt:
    await _ensure_unique(db, org_id, key, locale)
    prompt = Prompt(
        org_id=org_id,
        key=key,
        locale=locale,
        kind=kind,
        title_fa=title_fa,
        template=template,
        variables=variables or extract_variables(template),
        status=status,
        current_version=1,
        updated_by=user_id,
    )
    db.add(prompt)
    await db.flush()
    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=1,
            template=template,
            variables=prompt.variables,
            note="ایجاد اولیه",
            created_by=user_id,
        )
    )
    await db.flush()
    return prompt


async def update_prompt(
    db: AsyncSession,
    prompt: Prompt,
    *,
    template: str,
    title_fa: str | None = None,
    variables: list[str] | None = None,
    note: str | None = None,
    publish_now: bool = False,
    user_id: uuid.UUID | None = None,
) -> Prompt:
    prompt.current_version += 1
    prompt.template = template
    prompt.variables = variables or extract_variables(template)
    if title_fa:
        prompt.title_fa = title_fa
    if publish_now:
        prompt.status = "published"
    prompt.updated_by = user_id

    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=prompt.current_version,
            template=template,
            variables=prompt.variables,
            note=note,
            created_by=user_id,
        )
    )
    await db.flush()
    await db.refresh(prompt)  # updated_at is a server side default
    return prompt


async def publish_prompt(db: AsyncSession, prompt: Prompt) -> Prompt:
    expected = extract_variables(prompt.template)
    prompt.variables = expected
    prompt.status = "published"
    await db.flush()
    await db.refresh(prompt)
    return prompt


async def rollback_prompt(
    db: AsyncSession,
    prompt: Prompt,
    *,
    version: int,
    user_id: uuid.UUID | None = None,
) -> Prompt:
    """Rollback is append only: the old text becomes a *new* version."""
    target = (
        await db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_id == prompt.id, PromptVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError(code="prompt.version_not_found", params={"version": version})

    return await update_prompt(
        db,
        prompt,
        template=target.template,
        variables=list(target.variables or []),
        note=f"بازگشت به نسخه {version}",
        publish_now=True,
        user_id=user_id,
    )


async def list_versions(db: AsyncSession, prompt_id: uuid.UUID) -> list[PromptVersion]:
    return list(
        (
            await db.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_id == prompt_id)
                .order_by(PromptVersion.version.desc())
            )
        ).scalars()
    )


def summary(prompt: Prompt) -> dict[str, Any]:
    return {
        "id": str(prompt.id),
        "key": prompt.key,
        "version": prompt.current_version,
        "status": prompt.status,
        "scope": "global" if prompt.org_id is None else "org",
    }
