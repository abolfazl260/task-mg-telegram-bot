from __future__ import annotations

import sqlite3

from bot_context import get_current_bot_key
from config import ADMIN_IDS
from services.database import DB_PATH, execute, fetch_all, fetch_one, get_db

PERMISSION_KANBAN_PDF = "kanban_pdf_create"
PERMISSION_KANBAN_PDF_LABEL = "ایجاد PDF کانبان برد"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS permissions (
    permission_key TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS user_permissions (
    bot_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    permission_key TEXT NOT NULL REFERENCES permissions(permission_key) ON DELETE CASCADE,
    granted_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(bot_key, user_id, permission_key)
);
CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(bot_key, user_id);
"""


async def _ensure_schema() -> None:
    db = await get_db()
    await db.conn.executescript(_SCHEMA)
    await db.conn.commit()
    await execute(
        "INSERT OR IGNORE INTO permissions(permission_key,label,created_at) VALUES(?,?,datetime('now'))",
        (PERMISSION_KANBAN_PDF, PERMISSION_KANBAN_PDF_LABEL),
    )


def is_admin(user_id: object) -> bool:
    return str(user_id or "") in {str(item).strip() for item in ADMIN_IDS if str(item).strip()}


def _bot_key() -> str:
    return get_current_bot_key() or "default"


def has_permission_sync(user_id: object, permission_key: str) -> bool:
    """Synchronous read used only while building an inline keyboard."""
    if is_admin(user_id):
        return True
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        row = conn.execute(
            "SELECT 1 FROM user_permissions WHERE bot_key=? AND user_id=? AND permission_key=?",
            (_bot_key(), str(user_id), permission_key),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


async def has_permission(user_id: object, permission_key: str) -> bool:
    if is_admin(user_id):
        return True
    await _ensure_schema()
    row = await fetch_one(
        "user_permissions",
        "bot_key=? AND user_id=? AND permission_key=?",
        (_bot_key(), str(user_id), permission_key),
    )
    return row is not None


async def set_permission(user_id: object, permission_key: str, granted: bool) -> None:
    await _ensure_schema()
    uid = str(user_id)
    if granted:
        await execute(
            "INSERT OR REPLACE INTO user_permissions(bot_key,user_id,permission_key,granted_at) VALUES(?,?,?,datetime('now'))",
            (_bot_key(), uid, permission_key),
        )
    else:
        await execute(
            "DELETE FROM user_permissions WHERE bot_key=? AND user_id=? AND permission_key=?",
            (_bot_key(), uid, permission_key),
        )


async def list_users_for_permission(permission_key: str) -> list[dict]:
    await _ensure_schema()
    rows = await fetch_all("users")
    granted = await fetch_all(
        "user_permissions",
        "bot_key=? AND permission_key=?",
        (_bot_key(), permission_key),
    )
    granted_ids = {str(row.get("user_id")) for row in granted}
    for row in rows:
        row["has_permission"] = is_admin(row.get("user_id")) or str(row.get("user_id")) in granted_ids
    rows.sort(key=lambda row: (not row["has_permission"], (row.get("full_name") or row.get("user_id") or "").lower()))
    return rows
