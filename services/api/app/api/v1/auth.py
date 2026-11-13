"""Authentication endpoints.

Customers use ``/auth/otp/*`` (see ``app.api.v1.otp``); this module keeps the
password flow for platform staff plus the token lifecycle both flows share.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.accounts import resolve_org
from app.auth.otp import normalize_phone
from app.auth.sessions import client_ip, digest, issue_tokens, record_login_attempt
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, AuthError
from app.core.security import decode_token, verify_password
from app.core.text_fa import normalize_fa
from app.db.models import User, UserSession
from app.db.session import set_tenant
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _find_by_identifier(db: AsyncSession, org_id: uuid.UUID, identifier: str) -> User | None:
    """Staff sign in with an e-mail, customers may also use their mobile."""
    stmt = select(User).where(User.org_id == org_id)
    if "@" in identifier:
        stmt = stmt.where(User.email == identifier)
    else:
        try:
            stmt = stmt.where(User.phone == normalize_phone(identifier))
        except AppError:
            return None
    return (await db.execute(stmt)).scalar_one_or_none()


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    identifier = normalize_fa(payload.email).lower()
    org = await resolve_org(db, payload.org_slug)
    await set_tenant(db, org.id)

    user = await _find_by_identifier(db, org.id, identifier)

    if user is None or not user.password_hash or not verify_password(
        payload.password, user.password_hash
    ):
        await record_login_attempt(email=identifier, ip=client_ip(request), success=False)
        raise AuthError(code="auth.invalid_credentials")
    if not user.is_active:
        await record_login_attempt(email=identifier, ip=client_ip(request), success=False)
        raise AuthError(code="auth.user_inactive")

    user.last_login_at = datetime.now(UTC)
    tokens = await issue_tokens(user=user, db=db, request=request, settings=settings)
    await record_login_attempt(email=identifier, ip=client_ip(request), success=True)

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
                UserSession.refresh_hash == digest(payload.refresh_token),
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

    tokens = await issue_tokens(user=user, db=db, request=request, settings=settings)
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
                    UserSession.refresh_hash == digest(payload.refresh_token),
                    UserSession.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            row.revoked_at = datetime.now(UTC)
    return {"ok": True}
