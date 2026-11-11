"""row level security

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-09

Every tenant scoped table gets a policy based on ``app.org_id``. The application
role (``openbot_app``) is NOT a superuser and not the table owner, so policies
are always enforced; no tenant context means no rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "agents",
    "api_keys",
    "audit_logs",
    "conversations",
    "devices",
    "knowledge_bases",
    "mcp_servers",
    "memberships",
    "prompts",
    "providers",
    "runs",
    "sessions",
    "tool_invocations",
    "tools",
    "usage_ledger",
    "users",
    "wallets",
)

PREDICATE = """(
    current_setting('app.bypass_rls', true) = 'on'
    OR org_id IS NULL
    OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
)"""


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
            f"USING {PREDICATE} WITH CHECK {PREDICATE}"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
