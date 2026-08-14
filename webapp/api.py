"""Small, framework-independent Web App API primitives."""
from __future__ import annotations

from .auth import TelegramWebAppAuthError, TelegramWebAppUser, validate_init_data
from .config import WEBAPP_BOT_TOKEN


def authenticate_telegram_request(init_data: str) -> TelegramWebAppUser:
    """Validate a request's Telegram initData using the Web App bot token."""
    if not WEBAPP_BOT_TOKEN:
        raise TelegramWebAppAuthError("WEBAPP_BOT_TOKEN is not configured")
    return validate_init_data(init_data, WEBAPP_BOT_TOKEN)
