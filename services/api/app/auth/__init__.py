"""Authentication domain: accounts, sessions and phone OTP.

The HTTP layer (``app.api.v1.auth`` / ``app.api.v1.otp``) stays thin; everything
that decides *who the caller is* lives here so both the password flow (platform
staff) and the OTP flow (customers) share one implementation.
"""

from app.auth.accounts import find_or_create_by_phone, resolve_org
from app.auth.otp import issue_otp, verify_otp
from app.auth.sessions import issue_tokens, record_login_attempt

__all__ = [
    "find_or_create_by_phone",
    "issue_otp",
    "issue_tokens",
    "record_login_attempt",
    "resolve_org",
    "verify_otp",
]
