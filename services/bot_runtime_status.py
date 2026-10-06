"""Persistent runtime state for independently managed Bot Profiles."""
from __future__ import annotations

from datetime import datetime, timezone

from services.database import get_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_runtime_status (
    bot_key TEXT PRIMARY KEY,
    desired_status TEXT NOT NULL DEFAULT 'inactive',
    runtime_status TEXT NOT NULL DEFAULT 'stopped',
    last_started_at TEXT NOT NULL DEFAULT '',
    last_stopped_at TEXT NOT NULL DEFAULT '',
    last_reloaded_at TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    last_error_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ensure_runtime_status_schema() -> None:
    db = await get_db()
    async with db.lock:
        await db.conn.executescript(_SCHEMA)
        await db.conn.commit()


async def record_runtime_status(
    bot_key: str,
    runtime_status: str,
    *,
    desired_status: str,
    event: str = "",
    error: str = "",
    clear_error: bool = False,
) -> None:
    await ensure_runtime_status_schema()
    now = _now()
    started = now if event == "started" else ""
    stopped = now if event == "stopped" else ""
    reloaded = now if event == "reloaded" else ""
    error_at = now if error else ""
    clear_error_flag = 1 if clear_error else 0
    db = await get_db()
    async with db.lock:
        await db.conn.execute(
            """
            INSERT INTO bot_runtime_status(
                bot_key,desired_status,runtime_status,last_started_at,last_stopped_at,
                last_reloaded_at,last_error,last_error_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(bot_key) DO UPDATE SET
                desired_status=excluded.desired_status,
                runtime_status=excluded.runtime_status,
                last_started_at=CASE
                    WHEN excluded.last_started_at!='' THEN excluded.last_started_at
                    ELSE bot_runtime_status.last_started_at
                END,
                last_stopped_at=CASE
                    WHEN excluded.last_stopped_at!='' THEN excluded.last_stopped_at
                    ELSE bot_runtime_status.last_stopped_at
                END,
                last_reloaded_at=CASE
                    WHEN excluded.last_reloaded_at!='' THEN excluded.last_reloaded_at
                    ELSE bot_runtime_status.last_reloaded_at
                END,
                last_error=CASE
                    WHEN ?=1 THEN ''
                    WHEN excluded.last_error!='' THEN excluded.last_error
                    ELSE bot_runtime_status.last_error
                END,
                last_error_at=CASE
                    WHEN ?=1 THEN ''
                    WHEN excluded.last_error_at!='' THEN excluded.last_error_at
                    ELSE bot_runtime_status.last_error_at
                END,
                updated_at=excluded.updated_at
            """,
            (
                bot_key,
                desired_status,
                runtime_status,
                started,
                stopped,
                reloaded,
                error,
                error_at,
                now,
                clear_error_flag,
                clear_error_flag,
            ),
        )
        await db.conn.commit()


async def list_runtime_statuses() -> dict[str, dict]:
    await ensure_runtime_status_schema()
    db = await get_db()
    async with db.conn.execute("SELECT * FROM bot_runtime_status") as cur:
        return {row["bot_key"]: dict(row) for row in await cur.fetchall()}


async def get_runtime_status(bot_key: str) -> dict | None:
    await ensure_runtime_status_schema()
    db = await get_db()
    async with db.conn.execute(
        "SELECT * FROM bot_runtime_status WHERE bot_key=?",
        (bot_key,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None
