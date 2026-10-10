"""SQLite writer contention and startup regression tests for #233.

Every test uses a temporary database. No production path or user payloads.
"""
import asyncio
import logging
import sqlite3

import pytest

from services import database


@pytest.fixture
async def temp_db(tmp_path, monkeypatch):
    await database.close_all_dbs()
    database.shutdown_sync_loop()
    path = tmp_path / "contention.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    db = await database.get_db()
    await database.execute("INSERT INTO users(user_id,messages_count) VALUES('lock-user', 0)")
    yield db, path
    await database.close_all_dbs()
    database.shutdown_sync_loop()
    database._schema_ready_paths.discard(str(path))


@pytest.mark.asyncio
async def test_simultaneous_first_connect_per_loop_initializes_once(tmp_path, monkeypatch):
    await database.close_all_dbs()
    database.shutdown_sync_loop()
    path = tmp_path / "startup.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    before = await asyncio.gather(*(database.get_db() for _ in range(24)))
    assert len({id(db) for db in before}) == 1
    assert before[0].initialized
    async def another_loop():
        async def run():
            db = await database.get_db()
            result = await database.fetch_one_sql("SELECT COUNT(*) AS n FROM users")
            await database.close_db()
            return db.initialized, result["n"]
        return await asyncio.to_thread(lambda: asyncio.run(run()))
    # Different event loops share one schema and never collide on ALTER TABLE.
    initialized, count = await another_loop()
    assert initialized is False  # the separate loop explicitly closed its connection
    assert count == 0
    assert str(path) in database._schema_ready_paths
    await database.close_db()
    database._schema_ready_paths.discard(str(path))


@pytest.mark.asyncio
async def test_transient_external_writer_and_async_parallel_writes_are_exact(temp_db):
    _db, path = temp_db
    external = sqlite3.connect(path, timeout=0.1)
    external.execute("BEGIN IMMEDIATE")
    async def release():
        await asyncio.sleep(0.17)
        external.commit()
        external.close()
    async def write():
        return await database.execute(
            "UPDATE users SET messages_count=messages_count+1 WHERE user_id='lock-user'"
        )
    await asyncio.gather(release(), *(write() for _ in range(15)))
    row = await database.fetch_one("users", "user_id=?", ("lock-user",))
    assert row["messages_count"] == 15


@pytest.mark.asyncio
async def test_persistent_lock_exhausts_budget_logs_correlation_and_recovers(temp_db, monkeypatch, caplog):
    db, path = temp_db
    await db.conn.execute("PRAGMA busy_timeout=30")
    monkeypatch.setattr(database, "SQLITE_MAX_RETRIES", 2)
    monkeypatch.setattr(database, "_retry_delay", lambda attempt: 0.001)
    external = sqlite3.connect(path, timeout=0.1)
    external.execute("BEGIN IMMEDIATE")
    try:
        with caplog.at_level(logging.WARNING, logger=database.__name__), pytest.raises(sqlite3.OperationalError):
            await database.execute(
                "UPDATE users SET messages_count=messages_count+1 WHERE user_id='lock-user'"
            )
        rows = [r.message for r in caplog.records if "sqlite_contention" in r.message]
        assert len(rows) == 3
        assert all("correlation_id=" in msg and "operation=execute" in msg for msg in rows)
        assert "exhausted=True" in rows[-1]
        assert not any("lock-user" in msg for msg in rows)
    finally:
        external.rollback()
        external.close()
    assert (await database.fetch_one("users", "user_id=?", ("lock-user",)))["messages_count"] == 0
    await database.execute("UPDATE users SET messages_count=messages_count+1 WHERE user_id='lock-user'")
    assert (await database.fetch_one("users", "user_id=?", ("lock-user",)))["messages_count"] == 1


@pytest.mark.asyncio
async def test_failed_multi_statement_write_rolls_back_and_keeps_future_writes_safe(temp_db):
    with pytest.raises(sqlite3.IntegrityError):
        await database.transaction([
            ("UPDATE users SET messages_count=messages_count+1 WHERE user_id=?", ("lock-user",)),
            ("INSERT INTO users(user_id) VALUES(?)", ("lock-user",)),
        ])
    assert (await database.fetch_one("users", "user_id=?", ("lock-user",)))["messages_count"] == 0
    await database.transaction([
        ("UPDATE users SET messages_count=messages_count+1 WHERE user_id=?", ("lock-user",)),
        ("UPDATE users SET messages_count=messages_count+1 WHERE user_id=?", ("lock-user",)),
    ])
    assert (await database.fetch_one("users", "user_id=?", ("lock-user",)))["messages_count"] == 2


@pytest.mark.asyncio
async def test_returning_and_many_writes_commit_atomically(temp_db):
    result = await database.execute_returning_one(
        "INSERT INTO users(user_id) VALUES (?) RETURNING user_id", ("another-user",)
    )
    assert result == {"user_id": "another-user"}
    with pytest.raises(sqlite3.IntegrityError):
        await database.execute_many(
            "INSERT INTO users(user_id) VALUES (?)", [("batch-1",), ("lock-user",)]
        )
    assert await database.fetch_one("users", "user_id=?", ("batch-1",)) is None
    await database.execute_many(
        "INSERT INTO users(user_id) VALUES (?)", [("batch-1",), ("batch-2",)]
    )
    assert await database.fetch_one("users", "user_id=?", ("batch-2",)) is not None


@pytest.mark.asyncio
async def test_sync_bridge_uses_shared_async_writer_without_extra_sqlite_connection(temp_db, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unused synchronous writer connection created")
    # Only database.get_connection() is allowed to open a standalone sync conn;
    # compatibility _sync_sql() must delegate to the shared service.
    monkeypatch.setattr(database, "_configure_sync_connection", forbidden)
    await asyncio.to_thread(
        database._sync_sql,
        "UPDATE users SET messages_count=messages_count+1 WHERE user_id=?", ("lock-user",),
    )
    assert (await database.fetch_one("users", "user_id=?", ("lock-user",)))["messages_count"] == 1
