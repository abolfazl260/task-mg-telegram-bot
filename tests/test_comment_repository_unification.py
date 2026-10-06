from __future__ import annotations

from types import SimpleNamespace

import pytest

from services import comment_message_store, database, task_service


@pytest.fixture(autouse=True)
def reset_comment_repository(monkeypatch):
    monkeypatch.setattr(comment_message_store, "_SCHEMA_READY", False)


def _telegram_message(*, chat_id: int, message_id: int, text: str):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        caption="",
        photo=[],
        voice=None,
        audio=None,
        document=None,
        video=None,
        sticker=None,
        animation=None,
        contact=None,
        location=None,
    )


@pytest.mark.asyncio
async def test_telegram_and_core_comments_share_one_repository(test_db):
    task_id = await task_service.create_task_async(
        user_id="comment-owner",
        title="Unified comments",
        priority="medium",
        deadline="",
        category="",
        tags="",
    )

    telegram_added = await comment_message_store.add_comment_message_async(
        task_id,
        {"id": "comment-owner", "full_name": "Telegram User", "username": "telegram_user"},
        _telegram_message(chat_id=7001, message_id=9001, text="comment from telegram"),
    )
    assert telegram_added is True

    via_task_service = await task_service.get_task_comments_async(task_id)
    assert len(via_task_service) == 1
    assert via_task_service[0]["text"] == "comment from telegram"
    assert via_task_service[0]["source"] == "telegram"
    assert via_task_service[0]["chat_id"] == "7001"
    assert via_task_service[0]["message_id"] == 9001

    core_added = await task_service.add_task_comment_async(
        task_id,
        {"id": "comment-owner", "full_name": "Web User", "username": "web_user"},
        {"type": "text", "text": "comment from core/web"},
    )
    assert core_added is True

    via_repository = await comment_message_store.get_comment_messages_async(task_id)
    assert [comment["text"] for comment in via_repository] == [
        "comment from telegram",
        "comment from core/web",
    ]
    assert [comment["source"] for comment in via_repository] == ["telegram", "core"]


@pytest.mark.asyncio
async def test_legacy_telegram_comments_are_migrated_once_and_visible_everywhere(test_db):
    task_id = await task_service.create_task_async(
        user_id="legacy-comment-owner",
        title="Legacy Telegram comment",
        priority="medium",
        deadline="",
        category="",
        tags="",
    )

    await database.execute(
        """CREATE TABLE task_comments_v2 (
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
    await database.execute(
        """INSERT INTO task_comments_v2
        (bot_key, task_id, author_id, author_name, author_username, chat_id, message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "legacy-bot",
            task_id,
            "legacy-comment-owner",
            "Legacy User",
            "legacy_user",
            "8001",
            9101,
            "2026-10-01 10:00",
        ),
    )

    comments = await task_service.get_task_comments_async(task_id)
    assert len(comments) == 1
    assert comments[0]["source"] == "telegram"
    assert comments[0]["bot_key"] == "legacy-bot"
    assert comments[0]["chat_id"] == "8001"
    assert comments[0]["message_id"] == 9101

    # Re-running repository initialization must not duplicate migrated rows.
    comment_message_store._SCHEMA_READY = False
    comments_again = await comment_message_store.get_comment_messages_async(task_id)
    assert len(comments_again) == 1
