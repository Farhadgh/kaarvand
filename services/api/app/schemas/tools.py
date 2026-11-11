"""Tool registry schemas."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

ToolKind = Literal["builtin", "http", "mcp", "connector"]
RiskLevel = Literal["low", "medium", "high"]
ApprovalPolicy = Literal["auto", "confirm", "deny"]
Category = Literal[
    "general",
    "social",
    "office",
    "media",
    "finance",
    "phone",
    "web",
    "dev",
    "productivity",
    "devices",
]

_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{1,118}$")


class ToolCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=120)
    name_fa: str = Field(min_length=1, max_length=200)
    description_fa: str | None = Field(default=None, max_length=2000)
    kind: ToolKind = "http"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    approval_policy: ApprovalPolicy = "auto"
    category: Category = "general"
    is_enabled: bool = True
    secret: str | None = Field(default=None, max_length=4096)
    secret_label: str | None = Field(default=None, max_length=40)

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, value: str) -> str:
        if not _SLUG.match(value):
            raise ValueError("slug must be lowercase a-z, 0-9, dot, dash, underscore")
        return value


class ToolUpdate(BaseModel):
    name_fa: str | None = Field(default=None, min_length=1, max_length=200)
    description_fa: str | None = Field(default=None, max_length=2000)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    risk_level: RiskLevel | None = None
    approval_policy: ApprovalPolicy | None = None
    category: Category | None = None
    is_enabled: bool | None = None
    secret: str | None = Field(default=None, max_length=4096)
    secret_label: str | None = Field(default=None, max_length=40)


class ToolOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    slug: str
    name_fa: str
    description_fa: str | None
    kind: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    config: dict[str, Any]
    actions: list[dict[str, Any]]
    risk_level: str
    approval_policy: str
    category: str
    is_enabled: bool
    has_secret: bool = False
    secret_masked: str | None = None
    secret_label: str | None = None


class ToolTestIn(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolTestOut(BaseModel):
    ok: bool
    result: dict[str, Any]
    invocation_id: str | None = None


class LlmToolOut(BaseModel):
    """Exactly what we hand to the model's tool-calling API."""

    name: str
    description: str
    parameters: dict[str, Any]
    slug: str


class ActionOpOut(BaseModel):
    op: str
    title_fa: str
    required: list[str]


class McpServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    transport: Literal["http", "sse", "stdio"] = "http"
    url: str | None = Field(default=None, max_length=1000)
    command: str | None = Field(default=None, max_length=1000)
    token: str | None = Field(default=None, max_length=4096)
    is_enabled: bool = True


class McpServerOut(ORMModel):
    id: uuid.UUID
    name: str
    transport: str
    url: str | None
    command: str | None
    is_enabled: bool
    has_token: bool = False
    tools_cache: list[dict[str, Any]]
    last_synced_at: Any


class McpSyncOut(BaseModel):
    tools: list[dict[str, Any]]
    count: int
