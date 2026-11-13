"""User management schemas."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

Role = Literal["admin", "user"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^09\d{9}$")


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    role: Role = "user"
    phone: str | None = Field(default=None, max_length=20)
    locale: str = Field(default="fa", max_length=8)
    digits_pref: Literal["fa", "en"] = "fa"

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        email = value.strip().lower()
        if not _EMAIL.match(email):
            raise ValueError("invalid email")
        return email

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if not value:
            return value
        digits = value.strip()
        if not _PHONE.match(digits):
            raise ValueError("phone must be 09xxxxxxxxx")
        return digits


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    role: Role | None = None
    is_active: bool | None = None
    locale: str | None = Field(default=None, max_length=8)
    digits_pref: Literal["fa", "en"] | None = None


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str | None = None
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    is_phone_verified: bool = False
    has_password: bool = False
    locale: str
    digits_pref: str
    last_login_at: Any = None
    created_at: Any = None
