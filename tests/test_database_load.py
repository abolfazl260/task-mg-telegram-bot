"""Concurrent SQLite load test using a temporary database only.

This test intentionally creates many concurrent read/write operations to
exercise the database timeout, WAL and retry behavior without touching the
real application database.
"""

import asyncio
import sqlite3
import time

import aiosqlite
import pytest

from services import database


@pytest.mark.asyncio
async def test_concurrent_sqlite_load_uses_isolated_database(tmp_path, monkeypatch):
    db_path = tmp_path / "load_test.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    async with aiosqlite.connect(str(db_path), timeout=database.SQLITE_TIMEOUT_SECONDS) as conn:
        await conn.executescript(database.SCHEMA)
        await conn.execute(
            "INSERT INTO users (user_id, full_name) VALUES (?, ?)",
            ("load-test-user", "Load Test User"),
        )
        await conn.commit()

    async def worker(worker_id: int, operations: int = 25):
        conn = await aiosqlite.connect(
            str(db_path),
            timeout=database.SQLITE_TIMEOUT_SECONDS,
        )
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute(f"PRAGMA busy_timeout={database.SQLITE_BUSY_TIMEOUT_MS}")
        try:
            for operation in range(operations):
                await conn.execute(
                    "UPDATE users SET messages_count = messages_count + 1, last_seen = ? WHERE user_id = ?",
                    (f"worker-{worker_id}-{operation}", "load-test-user"),
                )
                await conn.commit()
                await asyncio.sleep(0)
        finally:
            await conn.close()

    workers = 100
    operations_per_worker = 25
    total_operations = workers * operations_per_worker
    started_at = time.perf_counter()

    print(f"\n[LOAD TEST] workers={workers} operations_per_worker={operations_per_worker}")
    print(f"[LOAD TEST] total database writes={total_operations}")
    print("[LOAD TEST] database=temporary pytest database (production DB untouched)")

    await asyncio.gather(
        *(worker(worker_id, operations_per_worker) for worker_id in range(workers))
    )

    elapsed = time.perf_counter() - started_at

    async with aiosqlite.connect(str(db_path)) as conn:
        row = await (await conn.execute(
            "SELECT messages_count FROM users WHERE user_id = ?",
            ("load-test-user",),
        )).fetchone()

    actual_count = row[0]
    assert actual_count == total_operations
    assert db_path.exists()

    print(f"[LOAD TEST] successful writes={actual_count}/{total_operations}")
    print(f"[LOAD TEST] failed writes=0")
    print(f"[LOAD TEST] elapsed={elapsed:.2f}s")
    print(f"[LOAD TEST] average write time={elapsed / total_operations:.6f}s")
    print("[LOAD TEST] RESULT=PASSED")

    # The temporary directory is removed by pytest after the test; no
    # production database path is used or modified.


@pytest.mark.asyncio
async def test_concurrent_sqlite_load_retries_locked_writes(tmp_path, monkeypatch):
    """Force short lock contention and verify the retry helper succeeds."""
    db_path = tmp_path / "retry_load_test.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    conn = sqlite3.connect(str(db_path), timeout=1)
    conn.executescript(database.SCHEMA)
    conn.execute(
        "INSERT INTO users (user_id, full_name) VALUES (?, ?)",
        ("retry-user", "Retry User"),
    )
    conn.commit()
    conn.close()

    lock = sqlite3.connect(str(db_path), timeout=1)
    lock.execute("BEGIN IMMEDIATE")

    released = asyncio.Event()

    async def release_lock():
        await asyncio.sleep(0.15)
        lock.commit()
        lock.close()
        released.set()

    async def write_after_contention():
        await asyncio.to_thread(
            database._sync_sql,
            "UPDATE users SET messages_count = messages_count + 1 WHERE user_id = ?",
            ("retry-user",),
        )

    print("\n[RETRY TEST] lock contention created")
    await asyncio.gather(write_after_contention(), release_lock())
    await released.wait()

    verify = sqlite3.connect(str(db_path))
    count = verify.execute(
        "SELECT messages_count FROM users WHERE user_id = ?",
        ("retry-user",),
    ).fetchone()[0]
    verify.close()

    assert count == 1

    print("[RETRY TEST] lock released and write retried successfully")
    print(f"[RETRY TEST] final messages_count={count}")
    print("[RETRY TEST] RESULT=PASSED")
