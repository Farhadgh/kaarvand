"""extensions

Revision ID: 0000
Revises:
Create Date: 2026-11-09

PostgreSQL extensions must exist before any table that uses them
(pgvector -> app.db.models.knowledge).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # extensions are shared objects; do not drop them on downgrade
    pass
