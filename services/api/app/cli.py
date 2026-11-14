"""Operational CLI: accounts (break-glass) and SMS/OTP delivery checks.

Run::

    python -m app.cli list-users
    python -m app.cli promote-admin admin@kaarvand.amigok.cloud
    python -m app.cli set-password admin@kaarvand.amigok.cloud [--password ***]
    python -m app.cli sms-check                 # balance, lines, patterns
    python -m app.cli sms-test 09121234567      # one real message

Why ``bypass_rls`` below: ``users`` is protected by *forced* row level security
(0008), so a statement executed without ``app.bypass_rls`` matches zero rows and
still reports success — exactly how migration 0014 left the only admin as
``owner`` and locked the panel.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import ADMIN_ROLE
from app.core.security import hash_password
from app.db.models import User
from app.db.session import dispose_engine, session_scope
from app.notifications.sms import account_report, send_otp

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


def _sms_summary(settings: Settings) -> None:
    key = "set" if settings.farazsms_api_key else "MISSING"
    print(
        f"gateway: {settings.farazsms_base_url}  key: {key}  "
        f"line: {settings.farazsms_sender or 'MISSING'}  "
        f"pattern: {settings.farazsms_otp_pattern or '(simple sms)'}  "
        f"enabled: {settings.sms_enabled}"
    )


async def sms_check() -> int:
    """What the gateway says about this key: balance, lines and patterns."""
    settings = get_settings()
    _sms_summary(settings)
    report = await account_report(settings)
    errors = report.get("errors") or {}

    balance = report.get("balance") or {}
    print(
        f"balance: {balance.get('balance_amount')} toman ({balance.get('balance_count')} messages)"
    )
    lines = report.get("lines") or []
    print("lines:", ", ".join(str(row.get("number")) for row in lines) or "none")

    patterns = (report.get("patterns") or {}).get("data") or []
    print("patterns:")
    for row in patterns:
        attrs = ", ".join(
            str(attr.get("var") or attr.get("name")) for attr in row.get("attributes") or []
        )
        print(f"  {row.get('code')}  {row.get('status')}  «{row.get('text')}»  [{attrs}]")

    for name, message in errors.items():
        print(f"error {name}: {message}", file=sys.stderr)
    return 1 if errors else 0


async def sms_test(phone: str) -> int:
    """Send one real message (dummy code 12345) to prove the line works."""
    settings = get_settings()
    _sms_summary(settings)
    if not settings.sms_enabled:
        print("APP_SMS_ENABLED is false: nothing was sent", file=sys.stderr)
        return 1

    delivered = await send_otp(phone, "12345", settings=settings)
    print(f"delivered={delivered}")
    if not delivered:
        print(
            "the gateway refused it: run `python -m app.cli sms-check` "
            "(line must be accessible, pattern must be approved)",
            file=sys.stderr,
        )
        return 1
    return 0


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

    commands.add_parser("sms-check", help="gateway balance, lines and OTP patterns")

    sms_test = commands.add_parser("sms-test", help="send one real test message")
    sms_test.add_argument("phone")
    return parser


async def _run(args: argparse.Namespace) -> int:
    try:
        if args.command == "list-users":
            return await list_users()
        if args.command == "promote-admin":
            return await promote_admin(args.email)
        if args.command == "sms-check":
            return await sms_check()
        if args.command == "sms-test":
            return await sms_test(args.phone)
        password = args.password or _prompt_password()
        return await set_password(args.email, password)
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(build_parser().parse_args(argv)))


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
