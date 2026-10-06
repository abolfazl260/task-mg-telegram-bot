from __future__ import annotations

import aiosqlite
import pytest

from services import database


@pytest.mark.asyncio
async def test_startup_migrates_legacy_task_comments_before_source_key_index(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "legacy-comments.db"

    conn = await aiosqlite.connect(path)
    try:
        await conn.executescript(
            """
            CREATE TABLE task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                author_id TEXT,
                author_name TEXT NOT NULL DEFAULT '',
                author_username TEXT NOT NULL DEFAULT '',
                content_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO task_comments(
                task_id, author_id, author_name, content_json, created_at
            ) VALUES(
                'legacy-task', 'legacy-user', 'Legacy User', '{}', '2026-10-01'
            );
            """
        )
        await conn.commit()
    finally:
        await conn.close()

    monkeypatch.setattr(database, "DB_PATH", path)
    db = database.Database()
    try:
        await db.connect()

        async with db.conn.execute("PRAGMA table_info(task_comments)") as cursor:
            columns = {row["name"] for row in await cursor.fetchall()}

        assert {
            "bot_key",
            "source",
            "source_key",
            "telegram_chat_id",
            "telegram_message_id",
        } <= columns

        async with db.conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_comments_source_key'"
        ) as cursor:
            assert await cursor.fetchone() is not None

        async with db.conn.execute(
            "SELECT task_id, author_name FROM task_comments WHERE id=1"
        ) as cursor:
            row = await cursor.fetchone()
        assert tuple(row) == ("legacy-task", "Legacy User")
    finally:
        await db.close()
