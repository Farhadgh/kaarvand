"""Password hashing and JWT helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.config import Settings, get_settings
from app.core.errors import AuthError

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except ValueError:
        return True


@dataclass(frozen=True, slots=True)
class TokenClaims:
    sub: str
    org_id: str | None
    role: str
    token_type: TokenType
    jti: str
    exp: int
    raw: dict[str, Any]


def _now() -> datetime:
    return datetime.now(UTC)


def create_token(
    *,
    subject: uuid.UUID | str,
    org_id: uuid.UUID | str | None,
    role: str,
    token_type: TokenType,
    settings: Settings | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    cfg = settings or get_settings()
    if token_type == "access":
        expires = _now() + timedelta(minutes=cfg.access_token_ttl_min)
    else:
        expires = _now() + timedelta(days=cfg.refresh_token_ttl_days)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "org": str(org_id) if org_id else None,
        "role": role,
        "typ": token_type,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(expires.timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_alg)


def decode_token(token: str, *, expected_type: TokenType | None = None) -> TokenClaims:
    cfg = get_settings()
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_alg])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError(code="auth.token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(code="auth.token_invalid") from exc

    token_type = payload.get("typ")
    if expected_type and token_type != expected_type:
        raise AuthError(code="auth.token_wrong_type")

    return TokenClaims(
        sub=payload["sub"],
        org_id=payload.get("org"),
        role=payload.get("role", "viewer"),
        token_type=token_type,
        jti=payload.get("jti", ""),
        exp=int(payload.get("exp", 0)),
        raw=payload,
    )
