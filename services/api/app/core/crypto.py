"""Symmetric encryption for provider / tool credentials (AES-256-GCM)."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings, get_settings
from app.core.errors import ConfigError

NONCE_SIZE = 12
KEY_SIZE = 32


def generate_master_key() -> str:
    """Return a fresh url-safe base64 master key (32 bytes)."""
    return base64.urlsafe_b64encode(os.urandom(KEY_SIZE)).decode()


def _decode_key(master_key: str) -> bytes:
    if not master_key:
        raise ConfigError(code="config.master_key_missing")
    try:
        key = base64.urlsafe_b64decode(master_key)
    except Exception as exc:  # noqa: BLE001 - any decode problem is a config problem
        raise ConfigError(code="config.master_key_invalid") from exc
    if len(key) != KEY_SIZE:
        raise ConfigError(code="config.master_key_invalid")
    return key


class SecretBox:
    """Encrypt/decrypt small secrets stored in Postgres ``BYTEA`` columns."""

    def __init__(self, master_key: str) -> None:
        self._aes = AESGCM(_decode_key(master_key))

    def encrypt(self, plaintext: str, *, aad: str = "") -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self._aes.encrypt(nonce, plaintext.encode("utf-8"), aad.encode() or None)
        return nonce + ciphertext

    def decrypt(self, blob: bytes, *, aad: str = "") -> str:
        if len(blob) <= NONCE_SIZE:
            raise ValueError("ciphertext too short")
        nonce, ciphertext = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
        return self._aes.decrypt(nonce, ciphertext, aad.encode() or None).decode("utf-8")

    def mask(self, secret: str) -> str:
        """Never send a raw secret to the client."""
        if len(secret) <= 8:
            return "****"
        return f"{secret[:4]}…{secret[-4:]}"


def get_secret_box(settings: Settings | None = None) -> SecretBox:
    return SecretBox((settings or get_settings()).master_key)
