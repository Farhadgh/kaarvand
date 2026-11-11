"""audio support

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-11 16:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICE = sa.Numeric(14, 10)
ZERO = sa.Integer()


def upgrade() -> None:
    # STT (per audio minute) and TTS (per 1K characters) prices
    op.add_column("models", sa.Column("audio_input_price", PRICE, nullable=True))
    op.add_column("models", sa.Column("audio_output_price", PRICE, nullable=True))
    op.add_column("price_history", sa.Column("audio_input_price", PRICE, nullable=True))
    op.add_column("price_history", sa.Column("audio_output_price", PRICE, nullable=True))

    # ledger keeps the units the customer was billed for
    op.add_column(
        "usage_ledger", sa.Column("audio_seconds", ZERO, nullable=False, server_default="0")
    )
    op.add_column(
        "usage_ledger", sa.Column("audio_chars", ZERO, nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("usage_ledger", "audio_chars")
    op.drop_column("usage_ledger", "audio_seconds")
    op.drop_column("price_history", "audio_output_price")
    op.drop_column("price_history", "audio_input_price")
    op.drop_column("models", "audio_output_price")
    op.drop_column("models", "audio_input_price")
