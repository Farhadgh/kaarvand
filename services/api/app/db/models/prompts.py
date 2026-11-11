"""Versioned prompts: every system prompt is a row, not a string in code."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey

PROMPT_KINDS = (
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
)


class Prompt(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "prompts"
    __table_args__ = (
        UniqueConstraint("org_id", "key", "locale", name="uq_prompts_org_key_locale"),
    )

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="fa", nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="agent.system", nullable=False)
    title_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    versions: Mapped[list["PromptVersion"]] = relationship(  # noqa: F821, UP037
        back_populates="prompt", cascade="all, delete-orphan"
    )


class PromptVersion(UUIDPrimaryKey, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_num"),)

    prompt_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    prompt: Mapped[Prompt] = relationship(back_populates="versions")


class PromptExample(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "prompt_examples"

    prompt_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
