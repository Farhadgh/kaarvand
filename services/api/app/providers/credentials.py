"""Provider credential handling (encrypted at rest, masked on the wire)."""

from __future__ import annotations

from typing import Any

from app.core.crypto import SecretBox, get_secret_box

AAD_PREFIX = "provider"


def _aad(provider: Any) -> str:
    return f"{AAD_PREFIX}:{getattr(provider, 'slug', '')}"


def encrypt_api_key(
    provider: Any, api_key: str | None, box: SecretBox | None = None
) -> bytes | None:
    if not api_key:
        return None
    return (box or get_secret_box()).encrypt(api_key, aad=_aad(provider))


def decrypt_api_key(provider: Any, box: SecretBox | None = None) -> str | None:
    blob: bytes | None = getattr(provider, "credentials_enc", None)
    if not blob:
        return None
    return (box or get_secret_box()).decrypt(blob, aad=_aad(provider))


def masked_api_key(provider: Any, box: SecretBox | None = None) -> str | None:
    secret = decrypt_api_key(provider, box)
    if not secret:
        return None
    return (box or get_secret_box()).mask(secret)


def scrub(provider: Any, text: str | None, box: SecretBox | None = None) -> str | None:
    """Remove the api key from provider error messages before storing/showing."""
    if not text:
        return text
    secret = decrypt_api_key(provider, box)
    if secret and secret in text:
        return text.replace(secret, "***")
    return text[:800]
