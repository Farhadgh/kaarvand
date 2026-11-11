"""inbound channels

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-10 11:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("inbound_channels", "inbound_events")
PREDICATE = """(
    current_setting('app.bypass_rls', true) = 'on'
    OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
)"""


def upgrade() -> None:
    op.create_table(
        "inbound_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reply_mode", sa.String(length=8), nullable=False),
        sa.Column("verify_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column("verify_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("events_count", sa.Integer(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_inbound_channels_slug"),
    )
    op.create_index("ix_inbound_channels_org", "inbound_channels", ["org_id"], unique=False)

    op.create_table(
        "inbound_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_id", sa.String(length=120), nullable=True),
        sa.Column("chat_id", sa.String(length=120), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("reply_status", sa.String(length=16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["inbound_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "external_id", name="uq_inbound_events_external"),
    )
    op.create_index(
        "ix_inbound_events_channel_time",
        "inbound_events",
        ["channel_id", "created_at"],
        unique=False,
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
            f"USING {PREDICATE} WITH CHECK {PREDICATE}"
        )


def downgrade() -> None:
    op.drop_index("ix_inbound_events_channel_time", table_name="inbound_events")
    op.drop_table("inbound_events")
    op.drop_index("ix_inbound_channels_org", table_name="inbound_channels")
    op.drop_table("inbound_channels")
