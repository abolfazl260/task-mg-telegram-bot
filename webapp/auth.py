"""Telegram Web App initData validation.

Telegram's initData must be validated on the server before its user identity
is trusted. This module deliberately does not access the database or bot
runtime; callers can use the returned user data to perform authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl
import json


class TelegramWebAppAuthError(ValueError):
    """Raised when Telegram Web App initData is invalid or expired."""


@dataclass(frozen=True)
class TelegramWebAppUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
    now: int | None = None,
) -> TelegramWebAppUser:
    """Validate Telegram Web App initData and return its trusted user.

    The function implements Telegram's Web App HMAC-SHA256 verification:
    fields are sorted by key, joined with newlines, and signed using a key
    derived from the bot token and the constant ``WebAppData``.
    """
    if not init_data or not bot_token:
        raise TelegramWebAppAuthError("Missing Telegram Web App authentication data")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramWebAppAuthError("Missing Telegram Web App hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    expected_hash = hmac.new(
        _secret_key(bot_token), data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise TelegramWebAppAuthError("Invalid Telegram Web App signature")

    try:
        auth_date = int(data["auth_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramWebAppAuthError("Invalid Telegram Web App auth_date") from exc

    current_time = int(time.time()) if now is None else now
    if auth_date > current_time or current_time - auth_date > max_age_seconds:
        raise TelegramWebAppAuthError("Expired Telegram Web App authentication data")

    try:
        raw_user = json.loads(data["user"])
        user_id = int(raw_user["id"])
        first_name = str(raw_user["first_name"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TelegramWebAppAuthError("Invalid Telegram Web App user data") from exc

    return TelegramWebAppUser(
        id=user_id,
        first_name=first_name,
        last_name=raw_user.get("last_name"),
        username=raw_user.get("username"),
        language_code=raw_user.get("language_code"),
    )
