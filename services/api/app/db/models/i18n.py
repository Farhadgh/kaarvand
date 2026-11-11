"""Admin editable UI strings (so Persian wording can change without a deploy)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey


class Translation(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "translations"
    __table_args__ = (UniqueConstraint("locale", "key", name="uq_translations_locale_key"),)

    locale: Mapped[str] = mapped_column(String(8), default="fa", nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    namespace: Mapped[str] = mapped_column(String(60), default="common", nullable=False)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
