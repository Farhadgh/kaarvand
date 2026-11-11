"""Usage / cost reporting schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel


class UsageBucket(BaseModel):
    key: str
    label: str
    runs: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    cost_irr: int


class UsageTotals(BaseModel):
    runs: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    cost_irr: int


class RunCounts(BaseModel):
    running: int = 0
    waiting_approval: int = 0
    failed: int = 0
    completed: int = 0


class UsageSummaryOut(BaseModel):
    """Everything the dashboard cards + charts need, in one call."""

    days: int
    fx_rate: int
    range_from: str
    range_to: str
    totals: UsageTotals
    by_day: list[UsageBucket]
    by_agent: list[UsageBucket]
    by_model: list[UsageBucket]
    runs: RunCounts
    agents_total: int
    agents_active: int
    devices_total: int
    devices_online: int
    pending_approvals: int
    budget: dict[str, int | None]


class UsageRow(BaseModel):
    at: str
    agent: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    cost_irr: int
    billable: bool
    org_id: uuid.UUID | None = None
