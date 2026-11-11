"""Credential encryption."""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from app.core.crypto import SecretBox, generate_master_key
from app.core.errors import ConfigError


def test_roundtrip() -> None:
    box = SecretBox(generate_master_key())
    blob = box.encrypt("sk-test-1234567890", aad="provider:1")
    assert blob != b"sk-test-1234567890"
    assert box.decrypt(blob, aad="provider:1") == "sk-test-1234567890"


def test_aad_mismatch_fails() -> None:
    box = SecretBox(generate_master_key())
    blob = box.encrypt("secret", aad="a")
    with pytest.raises(InvalidTag):
        box.decrypt(blob, aad="b")


def test_wrong_key_fails() -> None:
    box1 = SecretBox(generate_master_key())
    box2 = SecretBox(generate_master_key())
    blob = box1.encrypt("secret")
    with pytest.raises(InvalidTag):
        box2.decrypt(blob)


def test_mask_hides_secret() -> None:
    box = SecretBox(generate_master_key())
    masked = box.mask("sk-abcdefghijklmnop")
    assert "abcdefghij" not in masked
    assert masked.startswith("sk-a") and masked.endswith("mnop")


def test_missing_master_key_is_config_error() -> None:
    with pytest.raises(ConfigError) as exc:
        SecretBox("")
    assert exc.value.code == "config.master_key_missing"
