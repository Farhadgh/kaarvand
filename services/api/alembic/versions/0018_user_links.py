"""user account links: a customer's own social accounts

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-21 10:00:00.000000

Phase 5 lets a customer connect *their own* account (Facebook, Telegram Web,
WhatsApp Web, ...) and have an agent act as them. Three shapes share one table:

* ``auth_kind='browser'`` - the desktop app keeps a logged in browser profile and
  the agent drives it (no API key, no app review; works for personal accounts);
* ``auth_kind='session'`` - a protocol session such as Telegram MTProto;
* ``auth_kind='oauth'``   - a normal OAuth grant (LinkedIn, Google, Meta pages).

``account_links`` holds one row per (user, provider, external account). The
secrets (session string, access/refresh token) are encrypted with
``core/crypto.py`` and bound to ``link:{id}`` as AAD, so a copied row cannot be
decrypted by another link.

Children (assets / login attempts / observed messages) carry their own
``org_id`` like ``inbound_events`` does: row level security stays a plain column
comparison instead of a join.

Ownership is per user, not per org (the tenant *is* the platform), so
``devices`` and ``mcp_servers`` also gain an ``owner_user_id``: without it a
customer's link could be routed to another customer's laptop, and one customer
could bind another customer's MCP server to their agent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("account_links", "link_assets", "link_logins", "link_messages")
PREDICATE = """(
    current_setting('app.bypass_rls', true) = 'on'
    OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
)"""


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "account_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("auth_kind", sa.String(length=16), nullable=False),
        sa.Column("transport", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("phone_hint", sa.String(length=32), nullable=True),
        sa.Column("external_account_id", sa.String(length=160), nullable=True),
        sa.Column("session_enc", sa.LargeBinary(), nullable=True),
        sa.Column("access_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("refresh_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mcp_server_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "external_account_id",
            name="uq_account_links_user_provider",
        ),
    )
    op.create_index("ix_account_links_user_status", "account_links", ["user_id", "status"])
    op.create_index("ix_account_links_org_provider", "account_links", ["org_id", "provider"])

    op.create_table(
        "link_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["link_id"], ["account_links.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "link_id", "kind", "external_id", name="uq_link_assets_link_kind_external"
        ),
    )
    op.create_index("ix_link_assets_link", "link_assets", ["link_id"])

    op.create_table(
        "link_logins",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("challenge_enc", sa.LargeBinary(), nullable=True),
        sa.Column("qr_payload", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["link_id"], ["account_links.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_link_logins_link_time", "link_logins", ["link_id", "created_at"])

    op.create_table(
        "link_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("chat_id", sa.String(length=120), nullable=True),
        sa.Column("from_id", sa.String(length=120), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="accepted"),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["link_id"], ["account_links.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link_id", "external_id", name="uq_link_messages_link_external"),
    )
    op.create_index("ix_link_messages_link_time", "link_messages", ["link_id", "created_at"])

    op.add_column(
        "mcp_servers",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_mcp_servers_owner_user_id_users",
        "mcp_servers",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_mcp_servers_owner", "mcp_servers", ["owner_user_id"])

    op.add_column(
        "devices",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_devices_owner_user_id_users",
        "devices",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_devices_owner", "devices", ["owner_user_id"])

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
            f"USING {PREDICATE} WITH CHECK {PREDICATE}"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_devices_owner", table_name="devices")
    op.drop_constraint("fk_devices_owner_user_id_users", "devices", type_="foreignkey")
    op.drop_column("devices", "owner_user_id")

    op.drop_index("ix_mcp_servers_owner", table_name="mcp_servers")
    op.drop_constraint("fk_mcp_servers_owner_user_id_users", "mcp_servers", type_="foreignkey")
    op.drop_column("mcp_servers", "owner_user_id")

    op.drop_index("ix_link_messages_link_time", table_name="link_messages")
    op.drop_table("link_messages")
    op.drop_index("ix_link_logins_link_time", table_name="link_logins")
    op.drop_table("link_logins")
    op.drop_index("ix_link_assets_link", table_name="link_assets")
    op.drop_table("link_assets")
    op.drop_index("ix_account_links_org_provider", table_name="account_links")
    op.drop_index("ix_account_links_user_status", table_name="account_links")
    op.drop_table("account_links")
