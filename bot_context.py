"""Per-update bot context for isolating shared CSV storage by bot profile."""

from contextvars import ContextVar

_current_bot_key: ContextVar[str] = ContextVar("current_bot_key", default="default")


def set_current_bot_key(key: str):
    return _current_bot_key.set(key or "default")


def get_current_bot_key() -> str:
    return _current_bot_key.get()
