"""Resolve the bot profile used by Telegram Web App requests."""
from __future__ import annotations

import os

from bot_context import set_current_bot_key


class WebAppBotProfileError(ValueError):
    """Raised when a Web App request has no unambiguous bot profile."""


def get_webapp_bot_key() -> str:
    """Return the explicitly configured bot profile for the Web App.

    A Web App request has no Telegram Update context, so relying on the
    ContextVar default would silently select the ``default`` bot. Require an
    explicit profile instead when multiple bot profiles are configured.
    """
    key = (os.getenv("WEBAPP_BOT_KEY") or "").strip()
    if not key:
        raise WebAppBotProfileError("WEBAPP_BOT_KEY is not configured")
    return key


def set_webapp_bot_context() -> str:
    key = get_webapp_bot_key()
    set_current_bot_key(key)
    return key
