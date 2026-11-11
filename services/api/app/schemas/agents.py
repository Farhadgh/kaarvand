"""Agent / task / workflow schemas."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel

TriggerType = Literal["manual", "schedule", "webhook", "event", "inbound_call"]
MemoryMode = Literal["none", "short", "long"]
PermissionLevel = Literal["auto", "confirm", "deny"]

_CRON = re.compile(r"^(\S+\s+){4}\S+$")


def validate_cron(value: str) -> str:
    if not _CRON.match(value.strip()):
        raise ValueError("cron must have 5 fields")
    fields = value.split()
    limits = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    for field, (low, high) in zip(fields, limits, strict=True):
        if field in {"*", "?"}:
            continue
        for part in field.split(","):
            step = part.split("/")[0]
            if step in {"*", ""}:
                continue
            if "-" in step:
                start, _, end = step.partition("-")
                bounds = (start, end)
            else:
                bounds = (step, step)
            for item in bounds:
                if not item.isdigit() or not (low <= int(item) <= high):
                    raise ValueError(f"cron field out of range: {field}")
    return value.strip()


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    role: str = Field(default="assistant", max_length=60)
    avatar_url: str | None = Field(default=None, max_length=500)
    system_prompt_key: str = Field(default="agent.system.default", max_length=120)
    model_id: uuid.UUID | None = None
    temperature: Decimal = Field(default=Decimal("0.30"), ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=16, le=200_000)
    memory_mode: MemoryMode = "short"
    guardrails: dict[str, Any] = Field(default_factory=dict)
    monthly_budget_irr: int | None = Field(default=None, ge=0)
    is_active: bool = True


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, max_length=60)
    avatar_url: str | None = Field(default=None, max_length=500)
    system_prompt_key: str | None = Field(default=None, max_length=120)
    model_id: uuid.UUID | None = None
    temperature: Decimal | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=16, le=200_000)
    memory_mode: MemoryMode | None = None
    guardrails: dict[str, Any] | None = None
    monthly_budget_irr: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class AgentOut(ORMModel):
    id: uuid.UUID
    name: str
    role: str
    avatar_url: str | None
    system_prompt_key: str
    model_id: uuid.UUID | None
    model_external_id: str | None = None
    model_display_name_fa: str | None = None
    temperature: Decimal
    max_tokens: int
    memory_mode: str
    guardrails: dict[str, Any]
    monthly_budget_irr: int | None
    is_active: bool


class AgentTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    prompt_key: str | None = Field(default=None, max_length=120)
    prompt_template: str | None = Field(default=None, max_length=20000)
    inputs_schema: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    schedule_cron: str | None = Field(default=None, max_length=64)
    trigger_type: TriggerType = "manual"
    requires_approval: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def _validate(self) -> AgentTaskCreate:
        if not self.prompt_key and not self.prompt_template:
            raise ValueError("prompt_key or prompt_template is required")
        if self.trigger_type == "schedule":
            if not self.schedule_cron:
                raise ValueError("schedule_cron is required for schedule trigger")
            validate_cron(self.schedule_cron)
        return self


class AgentTaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    prompt_key: str | None = Field(default=None, max_length=120)
    prompt_template: str | None = Field(default=None, max_length=20000)
    inputs_schema: dict[str, Any] | None = None
    steps: list[dict[str, Any]] | None = None
    schedule_cron: str | None = Field(default=None, max_length=64)
    trigger_type: TriggerType | None = None
    requires_approval: bool | None = None
    is_active: bool | None = None

    @field_validator("schedule_cron")
    @classmethod
    def _cron(cls, value: str | None) -> str | None:
        return validate_cron(value) if value else value


class AgentTaskOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    prompt_key: str | None
    prompt_template: str | None
    inputs_schema: dict[str, Any]
    steps: list[dict[str, Any]]
    schedule_cron: str | None
    trigger_type: str
    requires_approval: bool
    is_active: bool
    last_run_at: Any
    # computed by the API (not stored): next fire time in UTC for scheduled tasks
    next_run_at: Any = None


class AgentToolIn(BaseModel):
    tool_id: uuid.UUID
    config: dict[str, Any] = Field(default_factory=dict)
    permission_level: PermissionLevel = "confirm"
    is_enabled: bool = True


class AgentToolOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    config: dict[str, Any]
    permission_level: str
    is_enabled: bool


class WorkflowIn(BaseModel):
    graph: dict[str, Any]
    activate: bool = True


class WorkflowOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    version: int
    graph: dict[str, Any]
    is_active: bool
