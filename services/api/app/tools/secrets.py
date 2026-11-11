"""Encrypted per-tool credentials."""

from __future__ import annotations

from typing import Any

from app.core.crypto import SecretBox, get_secret_box

AAD_PREFIX = "tool"


def _aad(tool: Any) -> str:
    return f"{AAD_PREFIX}:{getattr(tool, 'slug', '')}"


def encrypt_tool_secret(tool: Any, value: str | None, box: SecretBox | None = None) -> bytes | None:
    if not value:
        return None
    return (box or get_secret_box()).encrypt(value, aad=_aad(tool))


def decrypt_tool_secret(tool: Any, box: SecretBox | None = None) -> str | None:
    blob: bytes | None = getattr(tool, "secret_enc", None)
    if not blob:
        return None
    return (box or get_secret_box()).decrypt(blob, aad=_aad(tool))


def masked_secret(tool: Any, box: SecretBox | None = None) -> str | None:
    secret = decrypt_tool_secret(tool, box)
    if not secret:
        return None
    return (box or get_secret_box()).mask(secret)
