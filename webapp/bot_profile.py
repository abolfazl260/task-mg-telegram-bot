"""Resolve the bot profile used by Telegram Web App requests."""
from __future__ import annotations

from bot_context import set_current_bot_key


class WebAppBotProfileError(ValueError):
    """Raised when a Web App request has no valid bot profile."""


def get_webapp_bot_profile(bot_key: str):
    key = (bot_key or "").strip()
    if not key:
        raise WebAppBotProfileError("bot_key is required")
    # Import lazily to avoid coupling webapp configuration to bot startup.
    from bot_platform import load_bot_profiles

    for profile in load_bot_profiles():
        if profile.key == key:
            return profile
    raise WebAppBotProfileError("Unknown bot profile")


def get_webapp_bot_key(bot_key: str | None = None) -> str:
    """Return the explicitly selected bot profile for this Web App request."""
    key = (bot_key or "").strip()
    if not key:
        raise WebAppBotProfileError("bot_key is required")
    get_webapp_bot_profile(key)
    return key


def set_webapp_bot_context(bot_key: str) -> str:
    key = get_webapp_bot_key(bot_key)
    set_current_bot_key(key)
    return key
