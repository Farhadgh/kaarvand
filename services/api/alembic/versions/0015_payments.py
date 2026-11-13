"""wallet top-up payments (Zarinpal)

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-13 12:05:00.000000

A payment is created before the customer leaves for the gateway, so the row is
the source of truth for reconciliation: ``authority`` identifies it on the way
back, ``status`` tells whether the wallet was credited and ``reference`` keeps
the gateway receipt number for accounting.

The table is tenant scoped (RLS) like every other customer table; the public
callback looks the row up with ``app.bypass_rls`` and then re-binds the tenant
before writing.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREDICATE = """(
    current_setting('app.bypass_rls', true) = 'on'
    OR org_id IS NULL
    OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
)"""


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wallet_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gateway", sa.String(24), nullable=False),
        sa.Column("authority", sa.String(64), nullable=True),
        sa.Column("reference", sa.String(64), nullable=True),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("description_fa", sa.Text(), nullable=True),
        sa.Column("meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_payments_user_time", "payments", ["user_id", "created_at"])
    op.create_index("ix_payments_status_time", "payments", ["status", "created_at"])
    op.create_index(
        "uq_payments_gateway_authority",
        "payments",
        ["gateway", "authority"],
        unique=True,
    )

    op.execute("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON payments FOR ALL "
        f"USING {PREDICATE} WITH CHECK {PREDICATE}"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON payments")
    op.execute("ALTER TABLE payments NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments DISABLE ROW LEVEL SECURITY")
    op.drop_index("uq_payments_gateway_authority", table_name="payments")
    op.drop_index("ix_payments_status_time", table_name="payments")
    op.drop_index("ix_payments_user_time", table_name="payments")
    op.drop_table("payments")
