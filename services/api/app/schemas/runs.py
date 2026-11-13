"""Run schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RunStartIn(BaseModel):
    input: str = Field(min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    stream: bool = True
    max_tokens: int | None = Field(default=None, ge=64, le=10_000_000)


class RunApproveIn(BaseModel):
    stream: bool = True


class RunOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    task_id: uuid.UUID | None
    status: str
    trigger: str
    steps_taken: int
    tokens_in: int
    tokens_out: int
    #: the platform's own USD cost; hidden (null) for customers
    cost_usd: Decimal | None = None
    cost_irr: int
    fx_rate: Decimal | None
    error_code: str | None
    error_message: str | None
    started_at: Any
    finished_at: Any
    created_at: Any


class RunResultOut(BaseModel):
    run: RunOut
    text: str
    events: list[dict[str, Any]]


class ToolInvocationOut(ORMModel):
    id: uuid.UUID
    tool_slug: str
    args: dict[str, Any]
    result: dict[str, Any]
    status: str
    risk_level: str
    latency_ms: int | None
    approved_by: uuid.UUID | None
    created_at: Any


class RunEventsOut(BaseModel):
    run_id: uuid.UUID
    status: str
    events: list[dict[str, Any]]
