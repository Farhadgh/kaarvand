"""Session helpers: token pairs, refresh rows and login auditing."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_token
from app.db.models import LoginAttempt, User, UserSession
from app.db.session import get_session_factory
from app.schemas.auth import TokenPair


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


async def record_login_attempt(
    *,
    email: str | None = None,
    phone: str | None = None,
    ip: str | None = None,
    success: bool = False,
) -> None:
    """Separate session so a failed attempt is audited even when the request rolls back."""
    factory = get_session_factory()
    async with factory() as session:
        session.add(LoginAttempt(email=email, phone=phone, ip=ip, success=success))
        await session.commit()


async def issue_tokens(
    *,
    user: User,
    db: AsyncSession,
    request: Request | None,
    settings: Settings,
) -> TokenPair:
    access = create_token(
        subject=user.id,
        org_id=user.org_id,
        role=user.role,
        token_type="access",
        settings=settings,
    )
    refresh = create_token(
        subject=user.id,
        org_id=user.org_id,
        role=user.role,
        token_type="refresh",
        settings=settings,
    )
    db.add(
        UserSession(
            org_id=user.org_id,
            user_id=user.id,
            refresh_hash=digest(refresh),
            user_agent=request.headers.get("user-agent") if request else None,
            ip=client_ip(request),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_min * 60,
    )
