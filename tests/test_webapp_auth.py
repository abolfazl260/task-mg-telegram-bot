from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from webapp.auth import TelegramWebAppAuthError, validate_init_data

BOT_TOKEN = "123456:TEST_TOKEN"


def _make_init_data(*, auth_date: int, user: dict) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "AAExample",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_init_data_returns_user():
    data = _make_init_data(auth_date=1_700_000_000, user={"id": 42, "first_name": "Abolfazl"})
    user = validate_init_data(data, BOT_TOKEN, now=1_700_000_100)
    assert user.id == 42
    assert user.first_name == "Abolfazl"


def test_tampered_init_data_is_rejected():
    data = _make_init_data(auth_date=1_700_000_000, user={"id": 42, "first_name": "Abolfazl"})
    with pytest.raises(TelegramWebAppAuthError, match="signature"):
        validate_init_data(data.replace("Abolfazl", "Attacker"), BOT_TOKEN, now=1_700_000_100)


def test_expired_init_data_is_rejected():
    data = _make_init_data(auth_date=1_700_000_000, user={"id": 42, "first_name": "Abolfazl"})
    with pytest.raises(TelegramWebAppAuthError, match="Expired"):
        validate_init_data(data, BOT_TOKEN, now=1_700_000_001 + 86400)


def test_future_init_data_is_rejected():
    data = _make_init_data(auth_date=1_700_000_100, user={"id": 42, "first_name": "Abolfazl"})
    with pytest.raises(TelegramWebAppAuthError, match="Expired"):
        validate_init_data(data, BOT_TOKEN, now=1_700_000_000)
