"""App catalog: ready-made integrations (WhatsApp, Telegram, Office, ...).

The catalog is data, not code: a row describes *how* to talk to an app
(template for `tools.config` / `tools.actions`), what credentials the user must
provide, and which extra UI fields the panel should ask for. Installing an app
for an agent copies the template into a normal tenant `tools` row, so the run
engine, policy matrix and audit trail stay exactly the same.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey

APP_RUNTIMES = ("cloud", "desktop")
APP_CATEGORIES = ("social", "office", "productivity", "devices", "other")


class AppCatalog(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "app_catalog"
    __table_args__ = (UniqueConstraint("slug", name="uq_app_catalog_slug"),)

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `si:whatsapp`, `lucide:file-spreadsheet`, ... resolved by the panel
    icon: Mapped[str] = mapped_column(String(60), default="lucide:app-window", nullable=False)
    # brand colour for the icon tile (#25D366, ...)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    category: Mapped[str] = mapped_column(String(20), default="other", nullable=False)
    runtime: Mapped[str] = mapped_column(String(16), default="cloud", nullable=False)
    tool_kind: Mapped[str] = mapped_column(String(16), default="http", nullable=False)

    # template for tools.input_schema (what the model may send)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    # template for tools.config ({{placeholders}} filled by the install wizard)
    config_template: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    # template for tools.actions (desktop apps only)
    actions_template: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    # [{key, label_fa, required, secret, placeholder}] rendered by the wizard
    credentials: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    risk_level: Mapped[str] = mapped_column(String(8), default="medium", nullable=False)
    approval_policy: Mapped[str] = mapped_column(String(8), default="confirm", nullable=False)
    requires_device: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # how the connector detects the app on a customer machine
    detect: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    setup_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
