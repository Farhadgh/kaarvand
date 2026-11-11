"""Budget guards: monthly (Jalali month) and per run limits."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.jalali import gregorian_to_jalali, jalali_to_gregorian
from app.db.models import Agent, UsageLedger


def month_start(timezone: str = "Asia/Tehran") -> datetime:
    """First day of the current *Jalali* month, at local midnight."""
    now = datetime.now(ZoneInfo(timezone))
    jy, jm, _ = gregorian_to_jalali(now.year, now.month, now.day)
    gy, gm, gd = jalali_to_gregorian(jy, jm, 1)
    return datetime(gy, gm, gd, tzinfo=ZoneInfo(timezone))


async def spent_this_month_irr(
    db: AsyncSession, *, org_id: uuid.UUID, agent_id: uuid.UUID | None = None
) -> int:
    stmt = select(func.coalesce(func.sum(UsageLedger.cost_irr), 0)).where(
        UsageLedger.org_id == org_id,
        UsageLedger.created_at >= month_start(),
    )
    if agent_id is not None:
        stmt = stmt.where(UsageLedger.agent_id == agent_id)
    return int((await db.execute(stmt)).scalar() or 0)


async def ensure_budget(
    db: AsyncSession, *, agent: Agent, org_budget_irr: int | None = None
) -> None:
    agent_budget = agent.monthly_budget_irr
    if agent_budget:
        spent = await spent_this_month_irr(db, org_id=agent.org_id, agent_id=agent.id)
        if spent >= agent_budget:
            raise AppError(
                code="budget.agent_exceeded",
                status_code=409,
                params={"spent_irr": spent, "budget_irr": agent_budget},
            )

    if org_budget_irr:
        spent_org = await spent_this_month_irr(db, org_id=agent.org_id)
        if spent_org >= org_budget_irr:
            raise AppError(
                code="budget.org_exceeded",
                status_code=409,
                params={"spent_irr": spent_org, "budget_irr": org_budget_irr},
            )


def check_run_tokens(tokens_in: int, tokens_out: int, limit: int | None) -> None:
    if limit and (tokens_in + tokens_out) > limit:
        raise AppError(
            code="budget.token_limit",
            status_code=409,
            params={"tokens": tokens_in + tokens_out, "limit": limit},
        )


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
