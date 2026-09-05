from __future__ import annotations

import asyncio
import atexit
import sqlite3
import threading
import time
from pathlib import Path

import aiosqlite

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = (BASE_DIR / "data" / "data.db").resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
SQLITE_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_MAX_RETRIES = 6
SCHEMA = "PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=30000;"


class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None
        self.lock = asyncio.Lock()
        self.initialized = False

    async def connect(self):
        if self.conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = await aiosqlite.connect(
                str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS
            )
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys=ON")
            await self.conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
            await self.conn.execute("PRAGMA journal_mode=WAL")
            await self.conn.execute("PRAGMA synchronous=NORMAL")
        if not self.initialized:
            await self.conn.executescript(SCHEMA)
            await self.conn.commit()
            self.initialized = True
        return self.conn

    async def close(self):
        if self.conn is not None:
            conn = self.conn
            self.conn = None
            self.initialized = False
            await conn.close()


_db_by_loop: dict[asyncio.AbstractEventLoop, Database] = {}
_sync_loop: asyncio.AbstractEventLoop | None = None
_sync_thread: threading.Thread | None = None
_sync_loop_ready = threading.Event()
_sync_loop_lock = threading.Lock()


async def get_db() -> Database:
    loop = asyncio.get_running_loop()
    db = _db_by_loop.get(loop)
    if db is None:
        db = Database()
        _db_by_loop[loop] = db
    await db.connect()
    return db


async def init_db():
    await get_db()


async def close_db():
    loop = asyncio.get_running_loop()
    db = _db_by_loop.pop(loop, None)
    if db is not None:
        await db.close()


async def close_all_dbs():
    dbs = list(_db_by_loop.values())
    _db_by_loop.clear()
    for db in dbs:
        try:
            await db.close()
        except Exception:
            pass


def _start_sync_loop() -> asyncio.AbstractEventLoop:
    global _sync_loop, _sync_thread
    with _sync_loop_lock:
        if _sync_loop is not None and _sync_loop.is_running():
            return _sync_loop
        _sync_loop_ready.clear()

        def runner():
            global _sync_loop
            loop = asyncio.new_event_loop()
            _sync_loop = loop
            asyncio.set_event_loop(loop)
            _sync_loop_ready.set()
            try:
                loop.run_forever()
            finally:
                try:
                    loop.run_until_complete(close_all_dbs())
                except Exception:
                    pass
                loop.close()

        _sync_thread = threading.Thread(target=runner, name="db-sync-loop", daemon=True)
        _sync_thread.start()
    if not _sync_loop_ready.wait(timeout=10):
        raise RuntimeError("Timed out starting database compatibility event loop")
    if _sync_loop is None:
        raise RuntimeError("Database compatibility event loop failed to start")
    return _sync_loop


def _run(coro):
    """Bridge legacy synchronous callers without creating an event loop per call.

    Async application code should call the native async database API directly.
    When a legacy sync wrapper is reached from an active event loop, all such
    calls share one dedicated compatibility loop and one reusable DB connection
    instead of creating a new thread, selector and SQLite connection for every
    invocation. This prevents FD spikes when many handlers/jobs run together.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        async def runner_without_existing_loop():
            try:
                return await coro
            finally:
                await close_db()
        return asyncio.run(runner_without_existing_loop())

    loop = _start_sync_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def shutdown_sync_loop() -> None:
    """Close the compatibility DB and stop its dedicated loop/thread."""
    global _sync_loop, _sync_thread
    with _sync_loop_lock:
        loop, thread = _sync_loop, _sync_thread
        _sync_loop = None
        _sync_thread = None
    if loop is None:
        return
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(close_all_dbs(), loop)
        try:
            future.result(timeout=10)
        finally:
            loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread.is_alive():
        thread.join(timeout=10)


async def fetch_all(table, where="", params=()):
    db = await get_db()
    q = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
    async with db.conn.execute(q, tuple(params)) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def fetch_one(table, where, params=()):
    rows = await fetch_all(table, where, params)
    return rows[0] if rows else None


async def execute(sql, params=()):
    db = await get_db()
    async with db.lock:
        cur = await db.conn.execute(sql, tuple(params))
        await db.conn.commit()
        return cur.lastrowid


async def execute_many(sql, rows):
    db = await get_db()
    async with db.lock:
        await db.conn.executemany(sql, [tuple(r) for r in rows])
        await db.conn.commit()


async def transaction(statements):
    db = await get_db()
    async with db.lock:
        await db.conn.execute("BEGIN IMMEDIATE")
        try:
            for sql, p in statements:
                await db.conn.execute(sql, tuple(p))
            await db.conn.commit()
        except Exception:
            await db.conn.rollback()
            raise


def _is_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and any(
        marker in str(exc).lower() for marker in ("database is locked", "database table is locked", "database is busy")
    )


def _retry_delay(attempt: int) -> float:
    return min(0.25 * (2 ** attempt), 4.0)


def _configure_sync_connection(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")


def _sync_sql(sql, params=(), fetch="none"):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(SQLITE_MAX_RETRIES + 1):
        conn = sqlite3.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
        try:
            _configure_sync_connection(conn)
            cur = conn.execute(sql, tuple(params))
            if fetch == "one":
                out = cur.fetchone()
                result = dict(out) if out else None
            elif fetch == "all":
                result = [dict(r) for r in cur.fetchall()]
            else:
                result = cur.lastrowid
            conn.commit()
            return result
        except sqlite3.OperationalError as exc:
            last_error = exc
            try:
                conn.rollback()
            except Exception:
                pass
            if not _is_locked_error(exc) or attempt >= SQLITE_MAX_RETRIES:
                raise
            time.sleep(_retry_delay(attempt))
        finally:
            conn.close()
    raise last_error


def sync_all(table, where="", params=()):
    return _sync_sql(f"SELECT * FROM {table}" + (f" WHERE {where}" if where else ""), params, "all")


def sync_one(table, where, params=()):
    return _sync_sql(f"SELECT * FROM {table} WHERE {where}", params, "one")


def sync_execute(sql, params=()):
    return _sync_sql(sql, params, "none")


def sync_transaction(statements):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(SQLITE_MAX_RETRIES + 1):
        conn = sqlite3.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
        try:
            _configure_sync_connection(conn)
            conn.execute("BEGIN IMMEDIATE")
            for sql, p in statements:
                conn.execute(sql, tuple(p))
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            try:
                conn.rollback()
            except Exception:
                pass
            if not _is_locked_error(exc) or attempt >= SQLITE_MAX_RETRIES:
                raise
            time.sleep(_retry_delay(attempt))
        finally:
            conn.close()
    raise last_error


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
    _configure_sync_connection(conn)
    return conn


async def shutdown_database():
    await close_all_dbs()


def _atexit_cleanup():
    try:
        shutdown_sync_loop()
    except Exception:
        pass


atexit.register(_atexit_cleanup)
