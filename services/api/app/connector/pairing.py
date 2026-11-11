"""Device pairing and device tokens.

Flow: admin creates a device (short lived pairing code) -> connector posts the
code together with its public key -> receives a device token -> connects the
websocket with that token. No inbound port, no static IP, nothing to configure.
"""

from __future__ import annotations

import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import create_token, decode_token

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes
CODE_LENGTH = 8
PAIRING_TTL_MINUTES = 10


def new_pairing_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def pairing_expiry(minutes: int = PAIRING_TTL_MINUTES) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def normalize_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "").replace("-", "")


def codes_match(stored: str | None, provided: str) -> bool:
    if not stored:
        return False
    return hmac.compare_digest(normalize_code(stored), normalize_code(provided))


def is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


def issue_device_token(
    *,
    device_id: uuid.UUID,
    org_id: uuid.UUID,
    settings: Settings | None = None,
) -> str:
    return create_token(
        subject=device_id,
        org_id=org_id,
        role="device",
        token_type="access",
        settings=settings or get_settings(),
        extra={"kind": "device"},
    )


def read_device_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    claims = decode_token(token, expected_type="access")
    if claims.raw.get("kind") != "device" or not claims.org_id:
        raise AppError(code="device.invalid_token", status_code=401)
    return uuid.UUID(claims.sub), uuid.UUID(claims.org_id)
