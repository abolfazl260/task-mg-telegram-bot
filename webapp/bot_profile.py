"""Resolve the bot profile used by Telegram Web App requests."""
from __future__ import annotations

from bot_context import set_current_bot_key


class WebAppBotProfileError(ValueError):
    """Raised when a Web App request has no valid bot profile."""


def _available_profiles():
    # Import lazily to avoid coupling webapp configuration to bot startup.
    from bot_platform import load_bot_profiles
    return load_bot_profiles()


def get_webapp_bot_profile(bot_key: str | None = None):
    """Resolve a selected profile, falling back to the legacy/default bot.

    The admin Web App is normally opened from the primary bot and therefore
    does not need a bot_key in its URL. Custom-bot Web Apps can still pass an
    explicit bot_key and are validated normally.
    """
    key = (bot_key or "").strip()
    profiles = _available_profiles()
    if not key:
        for profile in profiles:
            if profile.key == "default":
                return profile
        if len(profiles) == 1:
            return profiles[0]
        raise WebAppBotProfileError("bot_key is required when multiple bot profiles are configured")
    for profile in profiles:
        if profile.key == key:
            return profile
    raise WebAppBotProfileError("Unknown bot profile")


def get_webapp_bot_key(bot_key: str | None = None) -> str:
    """Return the selected bot profile key, using the default when omitted."""
    return get_webapp_bot_profile(bot_key).key


def set_webapp_bot_context(bot_key: str | None = None) -> str:
    key = get_webapp_bot_key(bot_key)
    set_current_bot_key(key)
    return key
