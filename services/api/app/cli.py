"""Operational CLI for accounts: the break-glass path when the panel is locked.

Run::

    python -m app.cli list-users
    python -m app.cli promote-admin admin@kaarvand.amigok.cloud
    python -m app.cli set-password admin@kaarvand.amigok.cloud [--password ***]

Why this exists: ``users`` is protected by *forced* row level security (0008), so
a statement executed without ``app.bypass_rls`` matches zero rows and still
reports success — exactly how migration 0014 left the only admin as ``owner``
and locked the panel. Every query below therefore runs with ``bypass_rls=True``.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ADMIN_ROLE
from app.core.security import hash_password
from app.db.models import User
from app.db.session import dispose_engine, session_scope

MIN_PASSWORD_LENGTH = 8


async def _find_user(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    return result.scalar_one_or_none()


async def list_users() -> int:
    async with session_scope(bypass_rls=True) as db:
        users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()

    if not users:
        print("no accounts yet")
        return 0

    print(f"{'role':<6} {'active':<7} {'password':<9} {'email':<40} phone")
    for user in users:
        print(
            f"{user.role:<6} {str(user.is_active):<7} {str(user.has_password):<9} "
            f"{user.email or '-':<40} {user.phone or '-'}"
        )
    return 0


async def promote_admin(email: str) -> int:
    async with session_scope(bypass_rls=True) as db:
        user = await _find_user(db, email)
        if user is None:
            print(f"no account with email {email!r}", file=sys.stderr)
            return 1
        user.role = ADMIN_ROLE
        user.is_active = True
        print(f"{user.email}: role={user.role} active={user.is_active}")
    return 0


async def set_password(email: str, password: str) -> int:
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters",
            file=sys.stderr,
        )
        return 2

    async with session_scope(bypass_rls=True) as db:
        user = await _find_user(db, email)
        if user is None:
            print(f"no account with email {email!r}", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        user.is_active = True
        print(f"{user.email}: password updated (existing sessions expire on their own)")
    return 0


def _prompt_password() -> str:
    first = getpass.getpass("New password: ")
    again = getpass.getpass("Repeat password: ")
    if first != again:
        raise SystemExit("passwords do not match")
    return first


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Account maintenance for Kaarvand (runs with tenant RLS bypassed).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list-users", help="print every account with its role")

    promote = commands.add_parser(
        "promote-admin", help="give an account platform staff access to the panel"
    )
    promote.add_argument("email")

    reset = commands.add_parser("set-password", help="set a new password for an account")
    reset.add_argument("email")
    reset.add_argument("--password", help="skip the interactive prompt (for scripts)")
    return parser


async def _run(args: argparse.Namespace) -> int:
    try:
        if args.command == "list-users":
            return await list_users()
        if args.command == "promote-admin":
            return await promote_admin(args.email)
        password = args.password or _prompt_password()
        return await set_password(args.email, password)
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(build_parser().parse_args(argv)))


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
