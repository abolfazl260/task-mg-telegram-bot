import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from config import BOT_TOKEN


class TelegramWebAppAuthError(ValueError):
    pass


def validate_telegram_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """Validate Telegram Web App initData and return the parsed Telegram user."""

    if not init_data:
        raise TelegramWebAppAuthError("initData is required")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise TelegramWebAppAuthError("initData hash is required")

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramWebAppAuthError("initData hash is invalid")

    auth_date = int(pairs.get("auth_date") or 0)
    if max_age_seconds and time.time() - auth_date > max_age_seconds:
        raise TelegramWebAppAuthError("initData is expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise TelegramWebAppAuthError("initData user is required")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise TelegramWebAppAuthError("initData user is invalid") from exc

    if not user.get("id"):
        raise TelegramWebAppAuthError("Telegram user id is required")

    return user
