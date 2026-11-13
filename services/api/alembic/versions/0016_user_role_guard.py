"""exactly two user roles, and a panel that can never be locked out

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-13 19:40:00.000000

``0014`` collapsed the old ``owner`` role into ``admin`` with a plain ``UPDATE``.
That statement ran as the table owner while ``users`` carries *forced* row level
security (``0008``) and no tenant was bound, so PostgreSQL filtered every row
out: the rewrite matched nothing and reported success. The database kept a role
the API no longer knows, and the panel guard rejected the only admin account.

The repair below lifts row security for the duration of the rewrite (the
migration role owns the table, so no superuser is needed) and turns it back on
immediately. Two guarantees come with it:

* ``ck_users_role`` makes ``owner`` unwritable from any path — API, seeding or
  an ad hoc ``psql`` session;
* if no active admin is left, the oldest active account that can log in with a
  password is promoted, so the console never becomes unreachable.

**Any future data migration on a table listed in ``0008``/``0012``/``0015`` must
lift row security the same way, or it will silently change nothing.**
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOOTSTRAP_ADMIN = """
DO $$
DECLARE promoted text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin' AND is_active) THEN
        UPDATE users SET role = 'admin'
         WHERE id = (
                SELECT id FROM users
                 WHERE is_active AND password_hash IS NOT NULL
                 ORDER BY created_at
                 LIMIT 1
         )
         RETURNING email INTO promoted;
        RAISE NOTICE '0016: no active admin, promoted % to admin', promoted;
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    op.execute("UPDATE users SET role = 'admin' WHERE role = 'owner'")
    op.execute("UPDATE users SET role = 'user' WHERE role NOT IN ('admin', 'user')")
    op.execute(BOOTSTRAP_ADMIN)

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")

    op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'user')")


def downgrade() -> None:
    # The role rewrite is deliberately not undone: ``owner`` no longer exists in
    # the application, and reverting it would lock every admin out again.
    op.drop_constraint("ck_users_role", "users", type_="check")
