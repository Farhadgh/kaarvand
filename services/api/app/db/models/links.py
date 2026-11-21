"""A customer's own account, linked once so an agent can act as them.

``AccountLink`` is provider agnostic on purpose. The provider registry
(``app/links/providers.py``) decides *how* the authorization is obtained:

* ``browser`` - the desktop app keeps a logged in browser profile (Facebook,
  Telegram Web, WhatsApp Web); nothing secret reaches the server;
* ``session`` - a protocol session string (Telegram MTProto), encrypted here;
* ``oauth``   - access/refresh tokens from a normal OAuth grant.

``LinkAsset`` is what the link can act *on* (a page, a chat, a sheet). The user
picks an asset once; tools are generated per link and bound to the agent.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey

AUTH_KINDS = ("browser", "session", "oauth")
LINK_TRANSPORTS = ("device", "server")
LINK_STATUSES = ("pending", "active", "paused", "error", "revoked")
ASSET_KINDS = ("site", "page", "chat", "channel", "sheet", "calendar")


class AccountLink(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "account_links"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider", "external_account_id", name="uq_account_links_user_provider"
        ),
        Index("ix_account_links_user_status", "user_id", "status"),
        Index("ix_account_links_org_provider", "org_id", "provider"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # the owner: a link belongs to one customer, never to the tenant
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_kind: Mapped[str] = mapped_column(String(16), default="browser", nullable=False)
    transport: Mapped[str] = mapped_column(String(16), default="device", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_account_id: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # never plaintext; AAD is ``link:{id}`` so a copied row cannot be decrypted
    session_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True
    )

    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LinkAsset(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "link_assets"
    __table_args__ = (
        UniqueConstraint(
            "link_id", "kind", "external_id", name="uq_link_assets_link_kind_external"
        ),
        Index("ix_link_assets_link", "link_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("account_links.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), default="site", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LinkLogin(UUIDPrimaryKey, Base):
    """One attempt to establish a session (phone + code, QR, widget callback)."""

    __tablename__ = "link_logins"
    __table_args__ = (Index("ix_link_logins_link_time", "link_id", "created_at"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("account_links.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    challenge_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    qr_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LinkMessage(UUIDPrimaryKey, Base):
    """A message observed through a link (used when the agent listens, not only acts)."""

    __tablename__ = "link_messages"
    __table_args__ = (
        UniqueConstraint("link_id", "external_id", name="uq_link_messages_link_external"),
        Index("ix_link_messages_link_time", "link_id", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("account_links.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    chat_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="accepted", nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
