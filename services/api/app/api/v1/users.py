"""User management inside one organization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.wallet import get_or_create_wallet
from app.core.deps import get_db, require_admin
from app.core.errors import AppError, NotFoundError
from app.core.security import hash_password
from app.core.text_fa import normalize_fa
from app.db.models import User, UserSession
from app.schemas.users import PasswordResetIn, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
admin_only = require_admin
owner_only = require_admin


async def _get_user(db: AsyncSession, actor: User, user_id: uuid.UUID) -> User:
    target = (
        await db.execute(
            select(User).where(User.id == user_id, User.org_id == actor.org_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError(code="user.not_found")
    return target


@router.get("", response_model=list[UserOut])
async def list_users(
    role: str | None = None,
    is_active: bool | None = None,
    q: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(admin_only),
) -> list[UserOut]:
    stmt = select(User).where(User.org_id == actor.org_id)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if q:
        needle = f"%{normalize_fa(q)}%"
        stmt = stmt.where(or_(User.full_name.ilike(needle), User.email.ilike(needle)))
    rows = (await db.execute(stmt.order_by(User.created_at))).scalars().all()
    return [UserOut.model_validate(row) for row in rows]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(admin_only),
) -> UserOut:
    exists = (
        await db.execute(
            select(User.id).where(User.org_id == actor.org_id, User.email == payload.email)
        )
    ).first()
    if exists is not None:
        raise AppError(
            code="user.duplicate_email",
            status_code=409,
            params={"email": payload.email},
        )

    user = User(
        org_id=actor.org_id,
        email=payload.email,
        phone=payload.phone,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        locale=payload.locale,
        digits_pref=payload.digits_pref,
    )
    db.add(user)
    await db.flush()
    await get_or_create_wallet(db, org_id=actor.org_id, user_id=user.id)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def read_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(admin_only),
) -> UserOut:
    return UserOut.model_validate(await _get_user(db, actor, user_id))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(admin_only),
) -> UserOut:
    target = await _get_user(db, actor, user_id)
    data = payload.model_dump(exclude_unset=True)

    if target.id == actor.id and ("role" in data or data.get("is_active") is False):
        raise AppError(code="user.cannot_modify_self", status_code=409)

    for key, value in data.items():
        setattr(target, key, value)
    await db.flush()
    return UserOut.model_validate(target)


@router.post("/{user_id}/reset-password", response_model=UserOut)
async def reset_password(
    user_id: uuid.UUID,
    payload: PasswordResetIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(admin_only),
) -> UserOut:
    target = await _get_user(db, actor, user_id)

    target.password_hash = hash_password(payload.password)
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.flush()
    return UserOut.model_validate(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(owner_only),
) -> None:
    """Users are never deleted (audit trail) - they are deactivated."""
    target = await _get_user(db, actor, user_id)
    if target.id == actor.id:
        raise AppError(code="user.cannot_modify_self", status_code=409)
    target.is_active = False
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.flush()
    return None
