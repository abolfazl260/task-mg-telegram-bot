from __future__ import annotations

import base64
import json

import pytest

from services.secret_store import (
    SecretStoreError,
    decrypt_secret,
    encrypt_secret,
    encrypted_key_id,
    is_encrypted_secret,
    rewrap_secret,
    secret_storage_status,
)


def _key(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")


def _configure(monkeypatch, keys: dict[str, str], active: str | None = None) -> None:
    monkeypatch.setenv("BOT_TOKEN_ENCRYPTION_KEYS_JSON", json.dumps(keys))
    if active is None:
        monkeypatch.delenv("BOT_TOKEN_ACTIVE_KEY_ID", raising=False)
    else:
        monkeypatch.setenv("BOT_TOKEN_ACTIVE_KEY_ID", active)


def test_encrypt_decrypt_and_versioned_ciphertext(monkeypatch):
    _configure(monkeypatch, {"k1": _key(1)}, "k1")
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE12345"

    encrypted = encrypt_secret(secret)

    assert encrypted.startswith("enc:v1:k1:")
    assert secret not in encrypted
    assert is_encrypted_secret(encrypted)
    assert encrypted_key_id(encrypted) == "k1"
    assert decrypt_secret(encrypted) == secret
    assert secret_storage_status(encrypted) == "encrypted"


def test_missing_key_fails_closed_for_new_secret(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN_ENCRYPTION_KEYS_JSON", raising=False)
    monkeypatch.delenv("BOT_TOKEN_ACTIVE_KEY_ID", raising=False)
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE12345"

    with pytest.raises(SecretStoreError, match="bot_token_encryption_key_required") as exc:
        encrypt_secret(secret)

    assert secret not in str(exc.value)


def test_invalid_keyring_is_rejected_without_echoing_secret(monkeypatch, caplog):
    monkeypatch.setenv("BOT_TOKEN_ENCRYPTION_KEYS_JSON", '{"bad":"not-a-fernet-key"}')
    monkeypatch.setenv("BOT_TOKEN_ACTIVE_KEY_ID", "bad")
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE12345"

    with pytest.raises(SecretStoreError, match="invalid_bot_token_encryption_key"):
        encrypt_secret(secret)

    assert secret not in caplog.text


def test_plaintext_is_backward_compatible_until_keyring_is_configured(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN_ENCRYPTION_KEYS_JSON", raising=False)
    monkeypatch.delenv("BOT_TOKEN_ACTIVE_KEY_ID", raising=False)
    legacy = "123456:abcdefghijklmnopqrstuvwxyzABCDE12345"

    replacement, changed = rewrap_secret(legacy)

    assert changed is False
    assert replacement == legacy
    assert decrypt_secret(legacy) == legacy
    assert secret_storage_status(legacy) == "legacy_plaintext"


def test_rotation_rewraps_to_active_key(monkeypatch):
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE12345"
    _configure(monkeypatch, {"old": _key(1)}, "old")
    old_ciphertext = encrypt_secret(secret)
    assert encrypted_key_id(old_ciphertext) == "old"

    _configure(monkeypatch, {"old": _key(1), "new": _key(2)}, "new")
    replacement, changed = rewrap_secret(old_ciphertext)

    assert changed is True
    assert encrypted_key_id(replacement) == "new"
    assert decrypt_secret(replacement) == secret
    assert secret_storage_status(old_ciphertext) == "rotation_required"


def test_missing_decryption_key_fails_with_generic_error(monkeypatch):
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE12345"
    _configure(monkeypatch, {"old": _key(1)}, "old")
    ciphertext = encrypt_secret(secret)

    _configure(monkeypatch, {"new": _key(2)}, "new")
    with pytest.raises(SecretStoreError, match="bot_token_decryption_key_unavailable") as exc:
        decrypt_secret(ciphertext)

    assert secret not in str(exc.value)
    assert ciphertext not in str(exc.value)
