"""Authentication endpoints (tokens are handed to the Next.js BFF only)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.errors import AuthError
from app.core.security import create_token, decode_token, verify_password
from app.core.text_fa import normalize_fa
from app.db.models import LoginAttempt, Organization, User, UserSession
from app.db.session import get_session_factory, set_tenant
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _record_attempt(email: str, ip: str | None, success: bool) -> None:
    """Separate session so a failed login is still audited (no rollback)."""
    factory = get_session_factory()
    async with factory() as session:
        session.add(LoginAttempt(email=email, ip=ip, success=success))
        await session.commit()


async def _resolve_org(db: AsyncSession, org_slug: str | None) -> Organization:
    stmt = select(Organization).where(Organization.is_active.is_(True))
    if org_slug:
        stmt = stmt.where(Organization.slug == org_slug)
    org = (await db.execute(stmt.order_by(Organization.created_at).limit(1))).scalar_one_or_none()
    if org is None:
        raise AuthError(code="auth.org_not_found")
    return org


async def _issue_tokens(
    *,
    user: User,
    db: AsyncSession,
    request: Request,
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
            refresh_hash=_digest(refresh),
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_min * 60,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    email = normalize_fa(payload.email).lower()
    org = await _resolve_org(db, payload.org_slug)
    await set_tenant(db, org.id)

    user = (
        await db.execute(select(User).where(User.org_id == org.id, User.email == email))
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        await _record_attempt(email, _client_ip(request), success=False)
        raise AuthError(code="auth.invalid_credentials")
    if not user.is_active:
        await _record_attempt(email, _client_ip(request), success=False)
        raise AuthError(code="auth.user_inactive")

    user.last_login_at = datetime.now(UTC)
    tokens = await _issue_tokens(user=user, db=db, request=request, settings=settings)
    await _record_attempt(email, _client_ip(request), success=True)

    return LoginResponse(
        **tokens.model_dump(),
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    claims = decode_token(payload.refresh_token, expected_type="refresh")
    if not claims.org_id:
        raise AuthError(code="auth.token_invalid")

    await set_tenant(db, uuid.UUID(claims.org_id))
    session_row = (
        await db.execute(
            select(UserSession).where(
                UserSession.refresh_hash == _digest(payload.refresh_token),
                UserSession.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if session_row is None or session_row.expires_at <= now:
        raise AuthError(code="auth.session_expired")

    user = await db.get(User, uuid.UUID(claims.sub))
    if user is None or not user.is_active:
        raise AuthError(code="auth.user_inactive")

    tokens = await _issue_tokens(user=user, db=db, request=request, settings=settings)
    session_row.revoked_at = now  # rotate: one refresh token, one use
    return tokens


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if payload.refresh_token:
        row = (
            await db.execute(
                select(UserSession).where(
                    UserSession.refresh_hash == _digest(payload.refresh_token),
                    UserSession.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            row.revoked_at = datetime.now(UTC)
    return {"ok": True}
