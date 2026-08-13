"""Small, framework-independent Web App API primitives.

HTTP integration is intentionally kept separate from these primitives so the
project can adopt its existing runtime without duplicating business logic.
"""
from __future__ import annotations

import os

from .auth import TelegramWebAppAuthError, TelegramWebAppUser, validate_init_data


def authenticate_telegram_request(init_data: str) -> TelegramWebAppUser:
    """Validate a request's Telegram initData using the configured bot token."""
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise TelegramWebAppAuthError("BOT_TOKEN is not configured")
    return validate_init_data(init_data, bot_token)
