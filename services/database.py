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
SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 30000;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'UTC', date_format TEXT NOT NULL DEFAULT 'jalali',
    first_seen TEXT NOT NULL DEFAULT '', last_seen TEXT NOT NULL DEFAULT '', messages_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY, name TEXT NOT NULL, owner_id TEXT NOT NULL REFERENCES users(user_id),
    editor_code TEXT NOT NULL UNIQUE, viewer_code TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS team_members (
    team_id TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL, display_name TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '', joined_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(team_id,user_id)
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default', user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'medium', status TEXT NOT NULL DEFAULT 'pending', deadline TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT '',
    completed_at TEXT NOT NULL DEFAULT '', team_id TEXT REFERENCES teams(team_id) ON DELETE SET NULL,
    assignee_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, assignee_name TEXT NOT NULL DEFAULT '', assignee_username TEXT NOT NULL DEFAULT '',
    jira_key TEXT NOT NULL DEFAULT '', jira_sync_hash TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, author_name TEXT NOT NULL DEFAULT '', author_username TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS task_assignment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    actor_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, action TEXT NOT NULL DEFAULT '', old_assignee_name TEXT NOT NULL DEFAULT '',
    new_assignee_name TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS habits (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', repeat_type TEXT NOT NULL DEFAULT 'daily', target TEXT NOT NULL DEFAULT '',
    reminder_time TEXT NOT NULL DEFAULT '', start_date TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS habit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, done_date TEXT NOT NULL, done_at TEXT NOT NULL DEFAULT '',
    UNIQUE(habit_id,user_id,done_date)
);
CREATE TABLE IF NOT EXISTS external_connections (
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, bot_key TEXT NOT NULL, provider TEXT NOT NULL,
    access_token TEXT NOT NULL DEFAULT '', refresh_token TEXT NOT NULL DEFAULT '', expires_at TEXT NOT NULL DEFAULT '',
    external_list_id TEXT NOT NULL DEFAULT '', external_list_name TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 0,
    last_sync TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id,bot_key,provider)
);
CREATE TABLE IF NOT EXISTS jira_connections (
    bot_key TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, base_url TEXT NOT NULL,
    identity TEXT NOT NULL DEFAULT '', credential TEXT NOT NULL DEFAULT '', project_key TEXT NOT NULL, deployment TEXT NOT NULL DEFAULT 'cloud',
    issue_type TEXT NOT NULL DEFAULT 'Task', account_id TEXT NOT NULL DEFAULT '', auth_method TEXT NOT NULL DEFAULT 'basic',
    connected_at TEXT NOT NULL DEFAULT '', last_sync_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(bot_key,user_id)
);
CREATE TABLE IF NOT EXISTS jira_task_links (
    bot_key TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE, jira_key TEXT NOT NULL,
    sync_hash TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(bot_key,task_id), UNIQUE(bot_key,jira_key)
);
CREATE TABLE IF NOT EXISTS custom_bots (
    bot_key TEXT PRIMARY KEY, owner_user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE, owner_name TEXT NOT NULL DEFAULT '',
    owner_username TEXT NOT NULL DEFAULT '', bot_token TEXT NOT NULL DEFAULT '', bot_username TEXT NOT NULL DEFAULT '', features TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active', pricing_plan TEXT NOT NULL DEFAULT 'free_beta', created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS business_connections (
    id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, user_chat_id TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL DEFAULT '', date TEXT NOT NULL DEFAULT '', can_reply INTEGER NOT NULL DEFAULT 0, is_enabled INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS business_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL DEFAULT '', business_connection_id TEXT REFERENCES business_connections(id) ON DELETE CASCADE,
    chat_id TEXT NOT NULL DEFAULT '', message_id TEXT NOT NULL DEFAULT '', from_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
    from_username TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', message_ids_json TEXT NOT NULL DEFAULT '[]', date TEXT NOT NULL DEFAULT '', recorded_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_key ON tasks(bot_key);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_user ON tasks(bot_key,user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_status ON tasks(bot_key,status);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON tasks(team_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee_id ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_comments_task_id ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_assignment_task_id ON task_assignment_history(task_id);
CREATE INDEX IF NOT EXISTS idx_members_user_id ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_habits_user_id ON habits(user_id);
CREATE INDEX IF NOT EXISTS idx_habit_logs_user_date ON habit_logs(user_id,done_date);
CREATE INDEX IF NOT EXISTS idx_jira_links_key ON jira_task_links(jira_key);
CREATE INDEX IF NOT EXISTS idx_business_messages_connection ON business_messages(business_connection_id);
"""

class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None
        self.lock = asyncio.Lock()
        self.initialized = False

    async def connect(self):
        if self.conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = await aiosqlite.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
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

def _is_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and any(marker in str(exc).lower() for marker in ("database is locked", "database table is locked", "database is busy"))

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
            # Synchronous compatibility calls share the same async DB loop.
            # This keeps the reusable compatibility connection alive between calls.
            if fetch == "one":
                return _run(fetch_one_sql(sql, params))
            if fetch == "all":
                return _run(fetch_all_sql(sql, params))
            return _run(execute(sql, params))
        except sqlite3.OperationalError as exc:
            last_error = exc
            if not _is_locked_error(exc) or attempt >= SQLITE_MAX_RETRIES:
                raise
            time.sleep(_retry_delay(attempt))
        finally:
            conn.close()
    raise last_error

async def fetch_all_sql(sql, params=()):
    db = await get_db()
    async with db.conn.execute(sql, tuple(params)) as cur:
        return [dict(r) for r in await cur.fetchall()]

async def fetch_one_sql(sql, params=()):
    rows = await fetch_all_sql(sql, params)
    return rows[0] if rows else None

def sync_all(table, where="", params=()):
    return _run(fetch_all(table, where, params))

def sync_one(table, where, params=()):
    return _run(fetch_one(table, where, params))

def sync_execute(sql, params=()):
    return _run(execute(sql, params))

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

def sync_transaction(statements):
    return _run(transaction(statements))

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
