"""Small, framework-independent Web App API primitives."""
from __future__ import annotations

from .auth import TelegramWebAppUser, validate_init_data
from .bot_profile import get_webapp_bot_profile, set_webapp_bot_context


def authenticate_telegram_request(init_data: str, bot_key: str) -> TelegramWebAppUser:
    """Validate initData with the token belonging to the selected bot profile."""
    profile = get_webapp_bot_profile(bot_key)
    return validate_init_data(init_data, profile.token)


def set_request_bot_context(bot_key: str) -> str:
    return set_webapp_bot_context(bot_key)
