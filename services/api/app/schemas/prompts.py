"""Prompt schemas."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

PromptKind = Literal[
    "agent.system",
    "agent.task",
    "planner",
    "summarizer",
    "memory_extract",
    "guard_input",
    "guard_output",
    "tool_policy",
    "voice.persona",
    "rag.answer",
]

_PROMPT_KEY = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,118})$")


class PromptCreate(BaseModel):
    key: str = Field(min_length=2, max_length=120)
    title_fa: str = Field(min_length=1, max_length=200)
    template: str = Field(min_length=1, max_length=20000)
    kind: PromptKind = "agent.system"
    locale: str = Field(default="fa", max_length=8)
    variables: list[str] | None = None
    publish: bool = False

    @field_validator("key")
    @classmethod
    def _valid_key(cls, value: str) -> str:
        if not _PROMPT_KEY.match(value):
            raise ValueError("invalid prompt key")
        return value


class PromptUpdate(BaseModel):
    template: str = Field(min_length=1, max_length=20000)
    title_fa: str | None = Field(default=None, max_length=200)
    variables: list[str] | None = None
    note: str | None = Field(default=None, max_length=500)
    publish: bool = False


class PromptOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    key: str
    locale: str
    kind: str
    title_fa: str
    template: str
    variables: list[str]
    status: str
    current_version: int
    updated_at: Any


class PromptVersionOut(ORMModel):
    id: uuid.UUID
    version: int
    template: str
    variables: list[str]
    note: str | None
    created_at: Any


class PromptPreviewIn(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    agent_id: uuid.UUID | None = None


class PromptPreviewOut(BaseModel):
    key: str
    version: int
    template: str
    rendered: str
    variables: list[str]
    missing: list[str]


class RollbackIn(BaseModel):
    version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=500)
