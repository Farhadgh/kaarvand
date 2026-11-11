"""Agents, their workflows (graph as data), tasks and tool bindings."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey


class Agent(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (Index("ix_agents_org_active", "org_id", "is_active"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(60), default="assistant", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # prompt is referenced by key -> editing the prompt never touches the agent
    system_prompt_key: Mapped[str] = mapped_column(
        String(120), default="agent.system.default", nullable=False
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL"), nullable=True
    )
    temperature: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), default=Decimal("0.30"), nullable=False
    )
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    memory_mode: Mapped[str] = mapped_column(String(16), default="short", nullable=False)
    guardrails: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    monthly_budget_irr: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AgentWorkflow(UUIDPrimaryKey, TimestampMixin, Base):
    """Graph topology as data: node types are fixed, composition is dynamic."""

    __tablename__ = "agent_workflows"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_workflows_num"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    graph: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentTask(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (Index("ix_agent_tasks_agent", "agent_id"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    inputs_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTool(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_id", "tool_id", name="uq_agent_tools_pair"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    permission_level: Mapped[str] = mapped_column(String(12), default="confirm", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
