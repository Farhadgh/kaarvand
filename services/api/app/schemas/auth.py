"""Auth / user schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)
    org_slug: str | None = Field(default=None, max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str | None = None
    phone: str | None = None
    full_name: str
    role: str
    locale: str
    digits_pref: str
    is_phone_verified: bool = False
    has_password: bool = False


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(TokenPair):
    user: UserOut


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class OtpRequestOut(BaseModel):
    """Always 200 when a code was created; the SMS may still be delayed."""

    sent: bool = True
    expires_in: int
    resend_in: int
    sms_delivered: bool
    debug_code: str | None = None


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class OtpLoginResponse(LoginResponse):
    is_new_user: bool = False
