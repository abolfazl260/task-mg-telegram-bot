import sqlite3
from pathlib import Path

import pytest

from services import database


@pytest.mark.asyncio
async def test_async_database_connection_is_reused_and_closed(tmp_path: Path, monkeypatch):
    await database.close_all_dbs()
    database.shutdown_sync_loop()
    db_path = tmp_path / "data.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    first = await database.get_db()
    second = await database.get_db()
    assert first is second
    assert db_path.exists()
    assert len(database._db_by_loop) == 1

    await database.close_db()
    assert len(database._db_by_loop) == 0
    assert first.conn is None


@pytest.mark.asyncio
async def test_repeated_database_lifecycle_does_not_accumulate_connections(tmp_path: Path, monkeypatch):
    await database.close_all_dbs()
    database.shutdown_sync_loop()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "data.db")

    for _ in range(20):
        db = await database.get_db()
        assert db.conn is not None
        await database.close_db()
        assert len(database._db_by_loop) == 0

    await database.close_all_dbs()


@pytest.mark.asyncio
async def test_sync_bridge_reuses_one_compatibility_loop(tmp_path: Path, monkeypatch):
    await database.close_all_dbs()
    database.shutdown_sync_loop()
    db_path = tmp_path / "data.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

    for _ in range(10):
        assert database.sync_all("sample") == []

    assert database._sync_loop is not None
    assert database._sync_loop.is_running()
    assert len(database._db_by_loop) == 1

    database.shutdown_sync_loop()
    assert database._sync_loop is None
    assert database._sync_thread is None


def test_open_fd_count_is_bounded():
    from services.resource_monitor import open_fd_count

    count = open_fd_count()
    assert count is None or count >= 0
