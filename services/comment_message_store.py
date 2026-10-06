"""Canonical repository for task comments across Telegram, Web, and API.

The legacy `task_comments` table is the canonical store. Older Telegram-only
rows from `task_comments_v2` are migrated into it idempotently. Telegram
message references are retained so the original message can still be replayed,
while every channel reads the same normalized comment list.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from bot_context import get_current_bot_key
from services.database import execute, fetch_all, get_db


_TABLE = "task_comments"
_LEGACY_TELEGRAM_TABLE = "task_comments_v2"
_SCHEMA_READY = False


def _bot_key() -> str:
    return get_current_bot_key() or "default"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


async def _ensure_schema() -> None:
    """Add canonical metadata columns and migrate Telegram-only comments once."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    db = await get_db()
    async with db.lock:
        cur = await db.conn.execute(f"PRAGMA table_info({_TABLE})")
        columns = {row["name"] for row in await cur.fetchall()}
        additions = {
            "bot_key": "TEXT NOT NULL DEFAULT 'default'",
            "source": "TEXT NOT NULL DEFAULT 'core'",
            "source_key": "TEXT",
            "telegram_chat_id": "TEXT",
            "telegram_message_id": "INTEGER",
        }
        for name, definition in additions.items():
            if name not in columns:
                await db.conn.execute(f"ALTER TABLE {_TABLE} ADD COLUMN {name} {definition}")

        await db.conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{_TABLE}_source_key "
            f"ON {_TABLE}(source_key)"
        )

        cur = await db.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (_LEGACY_TELEGRAM_TABLE,),
        )
        if await cur.fetchone():
            cur = await db.conn.execute(
                f"""SELECT v.*
                    FROM {_LEGACY_TELEGRAM_TABLE} AS v
                    JOIN tasks AS t ON t.id = v.task_id
                    ORDER BY v.id"""
            )
            for raw in await cur.fetchall():
                row = dict(raw)
                source_key = (
                    f"telegram:{row.get('bot_key') or 'default'}:"
                    f"{row.get('chat_id')}:{row.get('message_id')}:{row.get('task_id')}"
                )
                content = {"type": "telegram_message"}
                await db.conn.execute(
                    f"""INSERT OR IGNORE INTO {_TABLE}
                    (task_id, author_id, author_name, author_username, content_json,
                     created_at, bot_key, source, source_key,
                     telegram_chat_id, telegram_message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'telegram', ?, ?, ?)""",
                    (
                        str(row.get("task_id") or ""),
                        str(row.get("author_id") or "") or None,
                        row.get("author_name") or "کاربر",
                        row.get("author_username") or "",
                        json.dumps(content, ensure_ascii=False),
                        row.get("created_at") or "",
                        row.get("bot_key") or "default",
                        source_key,
                        str(row.get("chat_id") or ""),
                        int(row.get("message_id") or 0),
                    ),
                )

        await db.conn.commit()
    _SCHEMA_READY = True


def _message_content(message) -> dict:
    text = getattr(message, "text", None)
    if text:
        return {"type": "text", "text": text}

    photo = getattr(message, "photo", None) or []
    if photo:
        return {"type": "photo", "caption": getattr(message, "caption", None) or ""}

    voice = getattr(message, "voice", None)
    if voice:
        return {"type": "voice", "caption": getattr(message, "caption", None) or ""}

    audio = getattr(message, "audio", None)
    if audio:
        return {
            "type": "audio",
            "file_name": getattr(audio, "file_name", None) or "",
            "caption": getattr(message, "caption", None) or "",
        }

    document = getattr(message, "document", None)
    if document:
        return {
            "type": "document",
            "file_name": getattr(document, "file_name", None) or "",
            "caption": getattr(message, "caption", None) or "",
        }

    video = getattr(message, "video", None)
    if video:
        return {
            "type": "video",
            "file_name": getattr(video, "file_name", None) or "",
            "caption": getattr(message, "caption", None) or "",
        }

    sticker = getattr(message, "sticker", None)
    if sticker:
        return {"type": "sticker", "emoji": getattr(sticker, "emoji", None) or ""}

    animation = getattr(message, "animation", None)
    if animation:
        return {
            "type": "animation",
            "file_name": getattr(animation, "file_name", None) or "",
            "caption": getattr(message, "caption", None) or "",
        }

    contact = getattr(message, "contact", None)
    if contact:
        name = " ".join(
            part
            for part in (
                getattr(contact, "first_name", None),
                getattr(contact, "last_name", None),
            )
            if part
        )
        return {
            "type": "contact",
            "text": name or getattr(contact, "phone_number", None) or "مخاطب",
        }

    location = getattr(message, "location", None)
    if location:
        return {
            "type": "location",
            "text": f"{getattr(location, 'latitude', '')},{getattr(location, 'longitude', '')}",
        }

    return {"type": "telegram_message", "caption": getattr(message, "caption", None) or ""}


async def add_comment_async(
    task_id: str,
    author: dict,
    content: dict,
    *,
    bot_key: str | None = None,
    source: str = "core",
    source_key: str | None = None,
    telegram_chat_id: str | None = None,
    telegram_message_id: int | None = None,
) -> bool:
    await _ensure_schema()
    payload = content if isinstance(content, dict) else {"content": content}
    await execute(
        f"""INSERT OR IGNORE INTO {_TABLE}
        (task_id, author_id, author_name, author_username, content_json, created_at,
         bot_key, source, source_key, telegram_chat_id, telegram_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(task_id),
            str(author.get("id") or author.get("user_id") or "") or None,
            author.get("full_name") or author.get("display_name") or "کاربر",
            author.get("username") or "",
            json.dumps(payload, ensure_ascii=False),
            _now(),
            bot_key or _bot_key(),
            source,
            source_key,
            str(telegram_chat_id) if telegram_chat_id is not None else None,
            int(telegram_message_id) if telegram_message_id is not None else None,
        ),
    )
    return True


async def add_comment_message_async(task_id: str, author: dict, message) -> bool:
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        chat_id = getattr(message, "chat_id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return False

    bot_key = _bot_key()
    source_key = f"telegram:{bot_key}:{chat_id}:{message_id}:{task_id}"
    return await add_comment_async(
        task_id,
        author,
        _message_content(message),
        bot_key=bot_key,
        source="telegram",
        source_key=source_key,
        telegram_chat_id=str(chat_id),
        telegram_message_id=int(message_id),
    )


async def get_comment_messages_async(task_id: str) -> list[dict]:
    await _ensure_schema()
    rows = await fetch_all(
        _TABLE,
        "task_id=? ORDER BY created_at, id",
        (str(task_id),),
    )
    comments: list[dict] = []
    for row in rows:
        try:
            content = json.loads(row.get("content_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            content = {}
        if not isinstance(content, dict):
            content = {"content": content}

        message_id = row.get("telegram_message_id")
        comments.append(
            {
                **content,
                "id": row.get("id"),
                "author_id": str(row.get("author_id") or ""),
                "author_name": row.get("author_name") or "کاربر",
                "author_username": row.get("author_username") or "",
                "created_at": row.get("created_at") or "",
                "bot_key": row.get("bot_key") or "default",
                "source": row.get("source") or "core",
                "chat_id": str(row.get("telegram_chat_id") or ""),
                "message_id": int(message_id or 0),
            }
        )
    return comments
