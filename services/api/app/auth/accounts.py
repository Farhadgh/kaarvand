"""Account lookup / creation shared by every sign-in path."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.wallet import get_or_create_wallet
from app.core.errors import AuthError
from app.db.models import Organization, User

CUSTOMER_ROLE = "user"


async def resolve_org(db: AsyncSession, org_slug: str | None = None) -> Organization:
    """The platform is one tenant; the slug is only needed for staging clones."""
    stmt = select(Organization).where(Organization.is_active.is_(True))
    if org_slug:
        stmt = stmt.where(Organization.slug == org_slug)
    org = (await db.execute(stmt.order_by(Organization.created_at).limit(1))).scalar_one_or_none()
    if org is None:
        raise AuthError(code="auth.org_not_found")
    return org


async def find_by_phone(db: AsyncSession, org_id: uuid.UUID, phone: str) -> User | None:
    return (
        await db.execute(select(User).where(User.org_id == org_id, User.phone == phone))
    ).scalar_one_or_none()


async def find_or_create_by_phone(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    phone: str,
) -> tuple[User, bool]:
    """Return ``(user, created)``; a first-time number becomes a customer."""
    user = await find_by_phone(db, org_id, phone)
    if user is not None:
        if not user.is_phone_verified:
            user.is_phone_verified = True
        return user, False

    user = User(
        org_id=org_id,
        phone=phone,
        email=None,
        password_hash=None,
        full_name=f"کاربر {phone[-4:]}",
        role=CUSTOMER_ROLE,
        is_phone_verified=True,
        locale="fa",
        digits_pref="fa",
    )
    db.add(user)
    await db.flush()
    await get_or_create_wallet(db, org_id=org_id, user_id=user.id)
    return user, True
