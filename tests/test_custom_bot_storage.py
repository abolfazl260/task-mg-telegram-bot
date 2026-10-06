from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio

from services import database
from services.custom_bot_service import create_custom_bot_request, read_custom_bots


@pytest_asyncio.fixture
async def isolated_custom_bot_db(tmp_path, monkeypatch):
    database.shutdown_sync_loop()
    await database.close_all_dbs()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "custom_bot_storage.db")
    await database.init_db()
    db = await database.get_db()
    await db.conn.execute(
        "INSERT INTO users(user_id,full_name,username) VALUES(?,?,?)",
        ("123", "Test User", "tester"),
    )
    await db.conn.commit()
    yield
    database.shutdown_sync_loop()
    await database.close_all_dbs()


@pytest.mark.asyncio
async def test_user_custom_bot_token_is_stored_plaintext(isolated_custom_bot_db):
    secret = "123456:abcdefghijklmnopqrstuvwxyzABCDE99999"
    user = SimpleNamespace(id=123, full_name="Test User", username="tester")

    created = create_custom_bot_request(user, secret, ["tasks", "teams"])

    db = await database.get_db()
    async with db.conn.execute(
        "SELECT bot_token FROM custom_bots WHERE bot_key=?",
        (created["bot_key"],),
    ) as cur:
        stored = (await cur.fetchone())[0]

    assert stored == secret

    runtime_rows = read_custom_bots(include_tokens=True)
    runtime = next(row for row in runtime_rows if row["bot_key"] == created["bot_key"])
    assert runtime["bot_token"] == secret

    public_rows = read_custom_bots(include_tokens=False)
    public = next(row for row in public_rows if row["bot_key"] == created["bot_key"])
    assert public["bot_token"] == ""
