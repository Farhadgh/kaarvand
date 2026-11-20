"""per-customer attribution for runs and the usage ledger

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-20 14:05:00.000000

Until now a run knew only its ``org_id``. On this platform the tenant *is* the
platform, so every customer could list every other customer's runs, and the
ledger could not answer "how much did this customer spend". Two nullable
columns fix that: ``runs.created_by`` and ``usage_ledger.user_id``.

Both tables carry *forced* row level security (``0008``), so the backfill lifts
it for the duration of the two ``UPDATE`` statements — otherwise PostgreSQL
filters every row out and the statements silently change nothing (the exact
trap that locked the admin out in ``0014``/``0016``).

Backfill rule: a run inherits the creator of its agent, and a ledger row
inherits the creator of its run. That attributes history to the account that
actually built the agent, which is the best information the old rows carry.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = ("runs", "usage_ledger")


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_runs_created_by_users", "runs", "users", ["created_by"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_runs_created_by_time", "runs", ["created_by", "created_at"])

    op.add_column(
        "usage_ledger",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_usage_ledger_user_id_users",
        "usage_ledger",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_usage_ledger_user_time", "usage_ledger", ["user_id", "created_at"])

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute(
        """
        UPDATE runs SET created_by = agents.created_by
          FROM agents
         WHERE runs.agent_id = agents.id
           AND runs.created_by IS NULL
        """
    )
    op.execute(
        """
        UPDATE usage_ledger SET user_id = runs.created_by
          FROM runs
         WHERE usage_ledger.run_id = runs.id
           AND usage_ledger.user_id IS NULL
        """
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_usage_ledger_user_time", table_name="usage_ledger")
    op.drop_constraint("fk_usage_ledger_user_id_users", "usage_ledger", type_="foreignkey")
    op.drop_column("usage_ledger", "user_id")

    op.drop_index("ix_runs_created_by_time", table_name="runs")
    op.drop_constraint("fk_runs_created_by_users", "runs", type_="foreignkey")
    op.drop_column("runs", "created_by")
