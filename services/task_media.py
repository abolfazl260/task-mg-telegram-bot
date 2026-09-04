from __future__ import annotations

import json
from datetime import datetime, timezone

from bot_context import get_current_bot_key
from services.database import execute, fetch_all

_TABLE = "task_media"
_SCHEMA_READY = False


def _bot_key():
    return get_current_bot_key() or "default"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


async def _ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    await execute(
        f"""CREATE TABLE IF NOT EXISTS {_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_key TEXT NOT NULL DEFAULT 'default',
            task_id TEXT NOT NULL,
            media_type TEXT NOT NULL,
            file_id TEXT,
            latitude REAL,
            longitude REAL,
            caption TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT ''
        )"""
    )
    await execute(f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_task ON {_TABLE}(bot_key, task_id, id)")
    _SCHEMA_READY = True


async def save_task_media_async(task_id: str, media_items: list[dict] | None):
    await _ensure_schema()
    for item in media_items or []:
        await execute(
            f"""INSERT INTO {_TABLE}
            (bot_key, task_id, media_type, file_id, latitude, longitude, caption, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _bot_key(),
                str(task_id),
                str(item.get("type") or ""),
                item.get("file_id"),
                item.get("latitude"),
                item.get("longitude"),
                str(item.get("caption") or ""),
                json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                _now(),
            ),
        )


async def get_task_media_async(task_id: str):
    await _ensure_schema()
    rows = await fetch_all(
        _TABLE,
        "bot_key=? AND task_id=? ORDER BY id",
        (_bot_key(), str(task_id)),
    )
    result = []
    for row in rows:
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
        except Exception:
            metadata = {}
        result.append({
            "type": row.get("media_type") or "",
            "file_id": row.get("file_id"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "caption": row.get("caption") or "",
            "metadata": metadata,
            "created_at": row.get("created_at") or "",
        })
    return result
