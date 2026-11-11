"""tool_secrets

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-09

HTTP tools need a credential (bearer token / api key). It is stored encrypted
(AES-256-GCM) and never returned by the API.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tools", sa.Column("secret_enc", sa.LargeBinary(), nullable=True))
    op.add_column("tools", sa.Column("secret_label", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("tools", "secret_label")
    op.drop_column("tools", "secret_enc")
