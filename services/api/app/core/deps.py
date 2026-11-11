"""FastAPI dependencies: db session, current user, tenant context."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_session_factory, set_tenant


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError(code="auth.missing_token")
    return authorization.split(" ", 1)[1].strip()


async def get_token_claims(authorization: str | None = Header(default=None)) -> dict:
    token = _bearer(authorization)
    claims = decode_token(token, expected_type="access")
    return {
        "user_id": claims.sub,
        "org_id": claims.org_id,
        "role": claims.role,
        "jti": claims.jti,
    }


async def get_current_user(
    claims: dict = Depends(get_token_claims),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not claims.get("org_id"):
        raise AuthError(code="auth.token_invalid")

    org_id = uuid.UUID(claims["org_id"])
    await set_tenant(db, org_id)

    user = await db.get(User, uuid.UUID(claims["user_id"]))
    if user is None:
        raise AuthError(code="auth.user_not_found")
    if not user.is_active:
        raise AuthError(code="auth.user_inactive")
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            from app.core.errors import ForbiddenError

            raise ForbiddenError(
                code="auth.insufficient_role",
                params={"required": sorted(allowed)},
            )
        return user

    return _dependency
