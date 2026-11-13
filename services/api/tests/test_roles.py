"""Roles are exactly ``admin`` and ``user`` — in the API *and* in the database.

Migration 0014 rewrote ``owner`` -> ``admin`` with a plain ``UPDATE`` while
``users`` carried *forced* row level security and no tenant was bound: the
statement matched zero rows and still reported success, so the only admin
account stayed ``owner`` and the panel guard locked it out of the console.

These tests pin the repair (migration 0016): the rewrite is really applied, the
database itself refuses a legacy role, and the break-glass CLI can always give an
account panel access again.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app import cli
from app.core.deps import ADMIN_ROLE, CUSTOMER_ROLE
from app.core.security import hash_password
from app.db.models import User
from app.db.session import session_scope


def _bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _count(db: Any, condition: Any) -> int:
    query = select(func.count()).select_from(User).where(condition)
    return int((await db.execute(query)).scalar_one())


async def test_seeded_admin_keeps_the_admin_role(client: Any, admin_tokens: dict[str, Any]) -> None:
    me = await client.get("/v1/auth/me", headers=_bearer(admin_tokens))
    assert me.status_code == 200, me.text
    assert me.json()["role"] == ADMIN_ROLE

    email = admin_tokens["user"]["email"]
    async with session_scope(bypass_rls=True) as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        assert user.role == ADMIN_ROLE
        assert user.is_active is True
        assert user.has_password is True


async def test_only_the_two_known_roles_exist() -> None:
    async with session_scope(bypass_rls=True) as db:
        legacy = await _count(db, User.role.not_in([ADMIN_ROLE, CUSTOMER_ROLE]))
        admins = await _count(db, User.role == ADMIN_ROLE)
    assert legacy == 0
    assert admins >= 1


async def test_database_rejects_the_legacy_owner_role(admin_tokens: dict[str, Any]) -> None:
    """``ck_users_role`` is the last line of defence: no code path can write ``owner``."""
    email = admin_tokens["user"]["email"]

    async with session_scope(bypass_rls=True) as db:
        with pytest.raises(IntegrityError):
            await db.execute(
                text("update users set role = 'owner' where email = :email"),
                {"email": email},
            )
        await db.rollback()

    async with session_scope(bypass_rls=True) as db:
        role = (await db.execute(select(User.role).where(User.email == email))).scalar_one()
    assert role == ADMIN_ROLE


async def test_panel_endpoints_need_the_admin_role(
    client: Any, auth_headers: dict[str, str], viewer_headers: dict[str, str]
) -> None:
    anonymous = await client.get("/v1/models")
    assert anonymous.status_code == 401

    customer = await client.get("/v1/models", headers=viewer_headers)
    assert customer.status_code == 403
    assert customer.json()["error"]["code"] == "auth.insufficient_role"

    staff = await client.get("/v1/models", headers=auth_headers)
    assert staff.status_code == 200


async def test_cli_promote_admin_restores_panel_access(
    client: Any, admin_tokens: dict[str, Any]
) -> None:
    email = f"staff-{uuid.uuid4().hex[:6]}@openbot.local"
    password = "staff-pass-123"

    async with session_scope(bypass_rls=True) as db:
        db.add(
            User(
                org_id=uuid.UUID(admin_tokens["user"]["org_id"]),
                email=email,
                full_name="کارشناس پشتیبانی",
                password_hash=hash_password(password),
                role=CUSTOMER_ROLE,
            )
        )

    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    blocked = await client.get("/v1/models", headers=_bearer(login.json()))
    assert blocked.status_code == 403

    assert await cli.promote_admin(email) == 0

    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    allowed = await client.get("/v1/models", headers=_bearer(login.json()))
    assert allowed.status_code == 200


async def test_cli_reports_unknown_accounts_and_short_passwords() -> None:
    assert await cli.promote_admin("nobody@openbot.local") == 1
    assert await cli.set_password("nobody@openbot.local", "short") == 2
