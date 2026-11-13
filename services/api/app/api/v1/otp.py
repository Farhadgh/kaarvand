"""Phone OTP sign-in: request a code, then exchange it for a token pair.

Customers never see a password form. The number becomes an account on the first
successful verification, and a Toman wallet is created at the same moment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    find_or_create_by_phone,
    issue_otp,
    issue_tokens,
    record_login_attempt,
    resolve_org,
    verify_otp,
)
from app.auth.otp import normalize_phone
from app.auth.sessions import client_ip
from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.core.errors import AuthError
from app.db.session import set_tenant
from app.notifications import send_otp
from app.schemas.auth import (
    OtpLoginResponse,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    UserOut,
)

router = APIRouter(prefix="/auth/otp", tags=["auth"])


@router.post("/request", response_model=OtpRequestOut)
async def request_code(
    payload: OtpRequestIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OtpRequestOut:
    phone = normalize_phone(payload.phone)
    _, code = await issue_otp(db, phone=phone, settings=settings, ip=client_ip(request))
    delivered = await send_otp(phone, code, settings=settings)
    # The code is echoed back only when SMS cannot be trusted to arrive (dev),
    # or when an operator explicitly turns on the debug switch.
    debug_code = code if (settings.otp_debug_code or not settings.sms_enabled) else None
    return OtpRequestOut(
        expires_in=settings.otp_ttl_seconds,
        resend_in=settings.otp_resend_cooldown_seconds,
        sms_delivered=delivered,
        debug_code=debug_code,
    )


@router.post("/verify", response_model=OtpLoginResponse)
async def verify_code(
    payload: OtpVerifyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OtpLoginResponse:
    phone = normalize_phone(payload.phone)
    try:
        await verify_otp(db, phone=phone, code=payload.code, settings=settings)
    except AuthError:
        await record_login_attempt(phone=phone, ip=client_ip(request), success=False)
        raise

    org = await resolve_org(db, None)
    await set_tenant(db, org.id)

    user, created = await find_or_create_by_phone(db, org_id=org.id, phone=phone)
    if not user.is_active:
        raise AuthError(code="auth.user_inactive")

    user.last_login_at = datetime.now(UTC)
    tokens = await issue_tokens(user=user, db=db, request=request, settings=settings)
    await record_login_attempt(phone=phone, ip=client_ip(request), success=True)

    return OtpLoginResponse(
        **tokens.model_dump(),
        user=UserOut.model_validate(user),
        is_new_user=created,
    )
