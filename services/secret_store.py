"""Core secret storage for managed Bot Profile credentials.

Ciphertext format:
    enc:v1:<key_id>:<fernet_token>

Keys are supplied through environment variables and are never persisted in the
database or repository. The active key is used for new writes; older keys remain
available only for decryption during rotation.
"""
from __future__ import annotations

import binascii
import json
import os
import re
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

KEYRING_ENV = "BOT_TOKEN_ENCRYPTION_KEYS_JSON"
ACTIVE_KEY_ENV = "BOT_TOKEN_ACTIVE_KEY_ID"
CIPHERTEXT_PREFIX = "enc:v1:"
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class SecretStoreError(ValueError):
    """Stable, non-secret-bearing error raised by the Core secret store."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SecretKeyring:
    active_key_id: str
    keys: dict[str, Fernet]


def _load_keyring() -> SecretKeyring | None:
    raw = os.getenv(KEYRING_ENV, "").strip()
    active = os.getenv(ACTIVE_KEY_ENV, "").strip()
    if not raw:
        if active:
            raise SecretStoreError("bot_token_encryption_keyring_missing")
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretStoreError("invalid_bot_token_keyring") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise SecretStoreError("invalid_bot_token_keyring")

    keys: dict[str, Fernet] = {}
    for key_id, encoded_key in parsed.items():
        key_id = str(key_id).strip()
        if not _KEY_ID_RE.match(key_id):
            raise SecretStoreError("invalid_bot_token_key_id")
        try:
            keys[key_id] = Fernet(str(encoded_key).strip().encode("ascii"))
        except (binascii.Error, ValueError, TypeError, UnicodeEncodeError) as exc:
            raise SecretStoreError("invalid_bot_token_encryption_key") from exc

    if not active:
        if len(keys) != 1:
            raise SecretStoreError("bot_token_active_key_required")
        active = next(iter(keys))
    if active not in keys:
        raise SecretStoreError("bot_token_active_key_unavailable")
    return SecretKeyring(active_key_id=active, keys=keys)


def keyring_configured() -> bool:
    return _load_keyring() is not None


def is_encrypted_secret(value: str) -> bool:
    return str(value or "").startswith(CIPHERTEXT_PREFIX)


def encrypted_key_id(value: str) -> str | None:
    value = str(value or "")
    if not is_encrypted_secret(value):
        return None
    parts = value.split(":", 3)
    if len(parts) != 4 or parts[0] != "enc" or parts[1] != "v1" or not parts[2]:
        raise SecretStoreError("invalid_bot_token_ciphertext")
    return parts[2]


def encrypt_secret(plaintext: str) -> str:
    plaintext = str(plaintext or "")
    if not plaintext:
        return ""
    keyring = _load_keyring()
    if keyring is None:
        raise SecretStoreError("bot_token_encryption_key_required")
    ciphertext = keyring.keys[keyring.active_key_id].encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{CIPHERTEXT_PREFIX}{keyring.active_key_id}:{ciphertext}"


def decrypt_secret(value: str, *, allow_legacy_plaintext: bool = True) -> str:
    value = str(value or "")
    if not value:
        return ""
    if not is_encrypted_secret(value):
        if allow_legacy_plaintext:
            return value
        raise SecretStoreError("legacy_plaintext_bot_token")

    parts = value.split(":", 3)
    if len(parts) != 4 or parts[0] != "enc" or parts[1] != "v1":
        raise SecretStoreError("invalid_bot_token_ciphertext")
    key_id, ciphertext = parts[2], parts[3]
    keyring = _load_keyring()
    if keyring is None:
        raise SecretStoreError("bot_token_encryption_key_required")
    fernet = keyring.keys.get(key_id)
    if fernet is None:
        raise SecretStoreError("bot_token_decryption_key_unavailable")
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise SecretStoreError("bot_token_decryption_failed") from exc


def rewrap_secret(value: str) -> tuple[str, bool]:
    """Migrate plaintext or old-key ciphertext to the active key."""
    value = str(value or "")
    if not value:
        return "", False
    keyring = _load_keyring()
    if keyring is None:
        if is_encrypted_secret(value):
            raise SecretStoreError("bot_token_encryption_key_required")
        return value, False

    if not is_encrypted_secret(value):
        return encrypt_secret(value), True

    key_id = encrypted_key_id(value)
    plaintext = decrypt_secret(value, allow_legacy_plaintext=False)
    if key_id == keyring.active_key_id:
        return value, False
    return encrypt_secret(plaintext), True


def secret_storage_status(value: str) -> str:
    value = str(value or "")
    if not value:
        return "none"
    if not is_encrypted_secret(value):
        return "legacy_plaintext"
    try:
        key_id = encrypted_key_id(value)
        keyring = _load_keyring()
    except SecretStoreError:
        return "unavailable"
    if keyring is None or key_id not in keyring.keys:
        return "unavailable"
    return "encrypted" if key_id == keyring.active_key_id else "rotation_required"
