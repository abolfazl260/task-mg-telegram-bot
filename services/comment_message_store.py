"""Persistent Telegram message references for task comments.

Comments are not stored as files, file_ids, or media-type payloads.  Each
comment points to the original Telegram message by bot_key + chat_id +
message_id so the message can be copied again later without storing its
content in SQLite.
"""

from datetime import datetime, timezone

from bot_context import get_current_bot_key
from services.database import execute, fetch_all


_TABLE = "task_comments_v2"
_SCHEMA_READY = False


async def _ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    await execute(
        f"""CREATE TABLE IF NOT EXISTS {_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_key TEXT NOT NULL DEFAULT 'default',
            task_id TEXT NOT NULL,
            author_id TEXT,
            author_name TEXT NOT NULL DEFAULT '',
            author_username TEXT NOT NULL DEFAULT '',
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT '',
            UNIQUE(bot_key, chat_id, message_id, task_id)
        )"""
    )
    await execute(f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_task ON {_TABLE}(bot_key, task_id, id)")
    _SCHEMA_READY = True


def _bot_key():
    return get_current_bot_key() or "default"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


async def add_comment_message_async(task_id: str, author: dict, message) -> bool:
    await _ensure_schema()
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return False

    await execute(
        f"""INSERT OR IGNORE INTO {_TABLE}
        (bot_key, task_id, author_id, author_name, author_username, chat_id, message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _bot_key(),
            str(task_id),
            str(author.get("id") or author.get("user_id") or "") or None,
            author.get("full_name") or author.get("display_name") or "کاربر",
            author.get("username") or "",
            str(chat_id),
            int(message_id),
            _now(),
        ),
    )
    return True


async def get_comment_messages_async(task_id: str):
    await _ensure_schema()
    return await fetch_all(
        _TABLE,
        "bot_key=? AND task_id=? ORDER BY id",
        (_bot_key(), str(task_id)),
    )
