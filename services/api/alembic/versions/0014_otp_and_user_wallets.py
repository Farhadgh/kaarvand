"""phone OTP accounts and per user wallets

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-13 09:20:00.000000

Two product decisions land here:

* customers sign up with a mobile number and an OTP (no email, no password), so
  ``users.email`` / ``users.password_hash`` become nullable and the unique
  constraints turn into partial indexes;
* a wallet belongs to a user instead of the whole organization, so the
  ``uq_wallets_org_id`` constraint is replaced by ``uq_wallets_user_id``.

Roles collapse to ``admin`` (platform staff) and ``user`` (customer); existing
rows are migrated in place so no account loses access.

Warning: the two ``UPDATE`` statements below are **silent no-ops on a real
database**. ``users`` has forced row level security (``0008``) and no tenant is
bound while alembic runs, so PostgreSQL filters every row out and the statements
still report success. ``0016`` re-runs the rewrite with row security lifted and
adds ``ck_users_role``; keep that pattern for future data migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: phone first accounts ---------------------------------------
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.add_column(
        "users",
        sa.Column("is_phone_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.drop_constraint("uq_users_org_email", "users", type_="unique")
    op.create_index(
        "uq_users_org_email",
        "users",
        ["org_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "uq_users_org_phone",
        "users",
        ["org_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    # --- roles: exactly two ------------------------------------------------
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'owner'")
    op.execute("UPDATE users SET role = 'user' WHERE role NOT IN ('admin', 'user')")

    # --- wallets belong to a user ------------------------------------------
    op.drop_constraint("uq_wallets_org_id", "wallets", type_="unique")
    op.add_column("wallets", sa.Column("user_id", PGUUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_wallets_user_id", "wallets", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(
        "uq_wallets_user_id",
        "wallets",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.alter_column(
        "wallets", "is_enabled", existing_type=sa.Boolean(), server_default=sa.true()
    )

    # --- login attempts can be phone based ---------------------------------
    op.alter_column("login_attempts", "email", existing_type=sa.String(255), nullable=True)
    op.add_column("login_attempts", sa.Column("phone", sa.String(20), nullable=True))
    op.create_index("ix_login_attempts_phone_time", "login_attempts", ["phone", "created_at"])

    # --- OTP codes ---------------------------------------------------------
    # Global table on purpose: it is written before the caller has a tenant.
    op.create_table(
        "otp_codes",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False, server_default="login"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_otp_codes_phone_time", "otp_codes", ["phone", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_otp_codes_phone_time", table_name="otp_codes")
    op.drop_table("otp_codes")

    op.drop_index("ix_login_attempts_phone_time", table_name="login_attempts")
    op.drop_column("login_attempts", "phone")
    op.alter_column("login_attempts", "email", existing_type=sa.String(255), nullable=False)

    op.alter_column("wallets", "is_enabled", existing_type=sa.Boolean(), server_default=None)
    op.drop_index("uq_wallets_user_id", table_name="wallets")
    op.drop_constraint("fk_wallets_user_id", "wallets", type_="foreignkey")
    op.drop_column("wallets", "user_id")
    op.create_unique_constraint("uq_wallets_org_id", "wallets", ["org_id"])

    op.execute("UPDATE users SET role = 'owner' WHERE role = 'admin'")

    op.drop_index("uq_users_org_phone", table_name="users")
    op.drop_index("uq_users_org_email", table_name="users")
    op.create_unique_constraint("uq_users_org_email", "users", ["org_id", "email"])
    op.drop_column("users", "is_phone_verified")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=False)
