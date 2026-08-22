from __future__ import annotations

import asyncio
import atexit
import sqlite3
from pathlib import Path

import aiosqlite

# Always resolve the database relative to the project, not the process CWD.
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = (BASE_DIR / "data" / "data.db").resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = "PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=10000;"


class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None
        self.lock = asyncio.Lock()
        self.initialized = False

    async def connect(self):
        if self.conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = await aiosqlite.connect(str(DB_PATH))
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys=ON")
            await self.conn.execute("PRAGMA busy_timeout=10000")
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


# Keep one async DB connection per long-lived event loop. Temporary loops created
# by compatibility code must close their DB before the loop exits.
_db_by_loop: dict[asyncio.AbstractEventLoop, Database] = {}


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
    """Close every async DB connection, including any compatibility-loop leftovers."""
    dbs = list(_db_by_loop.values())
    _db_by_loop.clear()
    for db in dbs:
        try:
            await db.close()
        except Exception:
            # Shutdown must continue even if one connection is already closed.
            pass


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


def _run(coro):
    """Run an async DB compatibility call from synchronous code without leaking DBs.

    The legacy sync wrappers are normally called from synchronous code. If one is
    reached while an event loop is active, run the coroutine in one short-lived
    worker thread, but explicitly close the worker loop's DB connection before
    asyncio.run() returns. The old implementation left that connection in the
    global loop map after every worker-loop invocation, causing file-descriptor
    exhaustion over time.
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

    import threading

    result = []
    error = []

    async def runner():
        try:
            result.append(await coro)
        except BaseException as exc:
            error.append(exc)
        finally:
            await close_db()

    def thread_runner():
        try:
            asyncio.run(runner())
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=thread_runner, name="db-sync-compat", daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0] if result else None


def _sync_sql(sql, params=(), fetch="none"):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
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
    finally:
        conn.close()


def sync_all(table, where="", params=()):
    return _sync_sql(f"SELECT * FROM {table}" + (f" WHERE {where}" if where else ""), params, "all")


def sync_one(table, where, params=()):
    return _sync_sql(f"SELECT * FROM {table} WHERE {where}", params, "one")


def sync_execute(sql, params=()):
    return _sync_sql(sql, params, "none")


def sync_transaction(statements):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("BEGIN IMMEDIATE")
        for sql, p in statements:
            conn.execute(sql, tuple(p))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH), timeout=10)


async def shutdown_database():
    await close_all_dbs()


atexit.register(lambda: _db_by_loop.clear())
