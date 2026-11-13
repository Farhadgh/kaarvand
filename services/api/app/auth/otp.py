"""Phone OTP: issuing, rate limiting and verification.

Design notes
------------
* Only a keyed hash of the code is stored; the plain code exists in memory and
  in the SMS.
* The most recent unconsumed code wins, so a resend invalidates the old one.
* Rate limits are enforced on the code table itself (no Redis in this stack):
  a cooldown per phone, a daily cap per phone and a daily cap per IP.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, AuthError
from app.core.text_fa import is_iran_mobile, to_latin_digits
from app.db.models import OtpCode
from app.db.session import get_session_factory

PURPOSE_LOGIN = "login"


def normalize_phone(value: str) -> str:
    """Accept ۰۹۱۲…, +98912…, 0098912… and always store 09xxxxxxxxx."""
    digits = to_latin_digits(str(value or "")).strip()
    for junk in (" ", "-", "(", ")", "\u200c"):
        digits = digits.replace(junk, "")
    if digits.startswith("+98"):
        digits = "0" + digits[3:]
    elif digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    if not is_iran_mobile(digits):
        raise AppError(code="auth.invalid_phone", status_code=422)
    return digits


def _code_hash(phone: str, code: str, settings: Settings) -> str:
    key = settings.jwt_secret.encode("utf-8")
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def generate_code(settings: Settings) -> str:
    length = max(4, min(8, settings.otp_length))
    return "".join(secrets.choice("0123456789") for _ in range(length))


async def _count_since(
    db: AsyncSession,
    *,
    since: datetime,
    phone: str | None = None,
    ip: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(OtpCode).where(OtpCode.created_at >= since)
    if phone is not None:
        stmt = stmt.where(OtpCode.phone == phone)
    if ip is not None:
        stmt = stmt.where(OtpCode.ip == ip)
    return int((await db.execute(stmt)).scalar_one())


async def issue_otp(
    db: AsyncSession,
    *,
    phone: str,
    settings: Settings,
    ip: str | None = None,
    purpose: str = PURPOSE_LOGIN,
) -> tuple[OtpCode, str]:
    """Create a code for ``phone`` and return ``(row, plain_code)``."""
    now = datetime.now(UTC)

    last = (
        await db.execute(
            select(OtpCode.created_at)
            .where(OtpCode.phone == phone)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed < settings.otp_resend_cooldown_seconds:
            raise AppError(
                code="otp.too_many_requests",
                status_code=429,
                params={"retry_after": int(settings.otp_resend_cooldown_seconds - elapsed) + 1},
            )

    day_ago = now - timedelta(days=1)
    if await _count_since(db, since=day_ago, phone=phone) >= settings.otp_daily_limit_per_phone:
        raise AppError(code="otp.daily_limit", status_code=429, params={"scope": "phone"})
    if ip and await _count_since(db, since=day_ago, ip=ip) >= settings.otp_daily_limit_per_ip:
        raise AppError(code="otp.daily_limit", status_code=429, params={"scope": "ip"})

    # a new code replaces every code still in flight for this number
    await db.execute(
        update(OtpCode)
        .where(OtpCode.phone == phone, OtpCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )

    code = generate_code(settings)
    row = OtpCode(
        phone=phone,
        code_hash=_code_hash(phone, code, settings),
        purpose=purpose,
        ip=ip,
        expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
    )
    db.add(row)
    await db.flush()
    return row, code


async def _bump_attempts(code_id: uuid.UUID, attempts: int) -> None:
    """Count a wrong guess in its own transaction.

    The request session rolls back when the code is rejected, so the counter has
    to be committed separately or brute force protection would never trigger.
    """
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            update(OtpCode).where(OtpCode.id == code_id).values(attempts=attempts)
        )
        await session.commit()


async def verify_otp(
    db: AsyncSession,
    *,
    phone: str,
    code: str,
    settings: Settings,
) -> OtpCode:
    """Check a code; the row is consumed on success and counted on failure."""
    row = (
        await db.execute(
            select(OtpCode)
            .where(OtpCode.phone == phone, OtpCode.consumed_at.is_(None))
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        raise AuthError(code="otp.code_not_found")

    now = datetime.now(UTC)
    if row.expires_at <= now:
        raise AuthError(code="otp.code_expired")

    if row.attempts >= settings.otp_max_attempts:
        raise AppError(code="otp.too_many_attempts", status_code=429)

    if not hmac.compare_digest(row.code_hash, _code_hash(phone, str(code).strip(), settings)):
        await _bump_attempts(row.id, row.attempts + 1)
        raise AuthError(code="otp.code_invalid")

    row.consumed_at = now
    row.attempts = row.attempts + 1
    await db.flush()
    return row
