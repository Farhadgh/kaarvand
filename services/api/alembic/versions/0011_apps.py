"""app_catalog

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-10 09:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column("name_en", sa.String(length=120), nullable=True),
        sa.Column("vendor", sa.String(length=120), nullable=True),
        sa.Column("description_fa", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=60), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("runtime", sa.String(length=16), nullable=False),
        sa.Column("tool_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "config_template", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "actions_template", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_level", sa.String(length=8), nullable=False),
        sa.Column("approval_policy", sa.String(length=8), nullable=False),
        sa.Column("requires_device", sa.Boolean(), nullable=False),
        sa.Column("detect", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("setup_fa", sa.Text(), nullable=True),
        sa.Column("docs_url", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_app_catalog_slug"),
    )
    op.create_index(
        "ix_app_catalog_category", "app_catalog", ["category", "sort_order"], unique=False
    )
    # app_catalog is a global dictionary: every tenant may read it, nobody edits it
    op.execute("ALTER TABLE app_catalog ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app_catalog FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY app_catalog_read ON app_catalog FOR SELECT USING (true)")
    bypass = "current_setting('app.bypass_rls', true) = 'on'"
    op.execute(
        f"CREATE POLICY app_catalog_admin ON app_catalog FOR ALL USING ({bypass}) "
        f"WITH CHECK ({bypass})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_catalog_admin ON app_catalog")
    op.execute("DROP POLICY IF EXISTS app_catalog_read ON app_catalog")
    op.drop_index("ix_app_catalog_category", table_name="app_catalog")
    op.drop_table("app_catalog")
