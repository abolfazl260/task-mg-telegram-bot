from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio

from services import database
from services.custom_bot_service import create_custom_bot_request, read_custom_bots


def _key() -> str:
    return base64.urlsafe_b64encode(bytes([9]) * 32).decode("ascii")


@pytest_asyncio.fixture
async def isolated_custom_bot_db(tmp_path, monkeypatch):
    database.shutdown_sync_loop()
    await database.close_all_dbs()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "custom_bot_encryption.db")
    monkeypatch.setenv("BOT_TOKEN_ENCRYPTION_KEYS_JSON", json.dumps({"test": _key()}))
    monkeypatch.setenv("BOT_TOKEN_ACTIVE_KEY_ID", "test")
    await database.init_db()
    yield
    database.shutdown_sync_loop()
    await database.close_all_dbs()


@pytest.mark.asyncio
async def test_user_custom_bot_token_is_encrypted_at_rest(isolated_custom_bot_db):
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE99999"
    user = SimpleNamespace(id=123, full_name="Test User", username="tester")

    created = create_custom_bot_request(user, secret, ["tasks", "teams"])

    db = await database.get_db()
    async with db.conn.execute(
        "SELECT bot_token FROM custom_bots WHERE bot_key=?",
        (created["bot_key"],),
    ) as cur:
        stored = (await cur.fetchone())[0]

    assert stored.startswith("enc:v1:test:")
    assert secret not in stored

    runtime_rows = read_custom_bots(include_tokens=True)
    runtime = next(row for row in runtime_rows if row["bot_key"] == created["bot_key"])
    assert runtime["bot_token"] == secret

    public_rows = read_custom_bots(include_tokens=False)
    public = next(row for row in public_rows if row["bot_key"] == created["bot_key"])
    assert public["bot_token"] == ""
