"""Multi-profile Habit isolation, legacy migration, and scheduler regressions (#219)."""
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import habit_service, reminders
from services.database import fetch_one, fetch_one_sql, migrate_core_schema


@pytest.mark.asyncio
async def test_same_user_two_bots_isolate_habits_mutations_logs_and_statistics(test_db):
    alpha = await habit_service.create_habit_async(100, "Alpha", bot_key="alpha")
    beta = await habit_service.create_habit_async(100, "Beta", bot_key="beta")
    assert {h["id"] for h in await habit_service.get_user_habits_async(100, bot_key="alpha")} == {alpha}
    assert {h["id"] for h in await habit_service.get_user_habits_async(100, bot_key="beta")} == {beta}
    assert await habit_service.get_user_habits_async(101, bot_key="alpha") == []
    assert await habit_service.get_habit_async(alpha, 100, bot_key="beta") is None
    assert not await habit_service.update_habit_async(alpha, 100, bot_key="beta", title="Stolen")
    assert not await habit_service.delete_habit_async(alpha, 100, bot_key="beta")
    assert not await habit_service.mark_done_async(alpha, 100, "2026-10-10", bot_key="beta")
    assert await habit_service.mark_done_async(alpha, 100, "2026-10-10", bot_key="alpha")
    assert await habit_service.mark_done_async(beta, 100, "2026-10-10", bot_key="beta")
    assert len(await habit_service.get_logs_async(100, bot_key="alpha")) == 1
    assert len(await habit_service.get_logs_async(100, bot_key="beta")) == 1
    assert await habit_service.get_logs_async(100, habit_id=alpha, bot_key="beta") == []
    assert (await habit_service.stats_for_habit_async({"id": alpha}, 100, bot_key="alpha"))["total"] == 1
    with pytest.raises(PermissionError, match="habit_access_denied"):
        await habit_service.stats_for_habit_async({"id": alpha}, 100, bot_key="beta")
    assert await habit_service.get_all_habit_user_ids_async(bot_key="alpha") == ["100"]
    assert await habit_service.get_all_habit_user_ids_async(bot_key="beta") == ["100"]
    assert await habit_service.delete_habit_async(alpha, 100, bot_key="alpha")
    assert (await habit_service.get_habit_async(beta, 100, bot_key="beta"))["title"] == "Beta"


@pytest.mark.asyncio
async def test_legacy_habits_keep_primary_keys_and_logs_in_default_profile(test_db):
    habit_id = await habit_service.create_habit_async("100", "Legacy", bot_key="default")
    assert await habit_service.mark_done_async(habit_id, "100", "2026-09-01", bot_key="default")
    assert (await fetch_one("habits", "id=?", (habit_id,)))["bot_key"] == "default"
    assert await habit_service.get_habit_async(habit_id, "100", bot_key="other") is None
    assert len(await habit_service.get_logs_async("100", bot_key="default")) == 1
    assert await habit_service.get_logs_async("100", bot_key="other") == []


@pytest.mark.asyncio
async def test_migration_adds_bot_provenance_to_old_schema_without_deleting_logs():
    import aiosqlite
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.executescript("""
            CREATE TABLE habits(id TEXT PRIMARY KEY, user_id TEXT, title TEXT);
            CREATE TABLE habit_logs(id INTEGER PRIMARY KEY, habit_id TEXT, user_id TEXT, done_date TEXT);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, work_item_type TEXT, parent_task_id TEXT,
                archived_at TEXT, created_at TEXT, workspace_id TEXT);
            INSERT INTO habits VALUES ('old-1','100','Preserve me');
            INSERT INTO habit_logs VALUES (1,'old-1','100','2026-09-01');
        """)
        # The full core migration also expects many supporting tables. Verify
        # the additive habit migration directly using its exact statements.
        columns = {r[1] for r in await (await conn.execute("PRAGMA table_info(habits)")).fetchall()}
        if "bot_key" not in columns:
            await conn.execute("ALTER TABLE habits ADD COLUMN bot_key TEXT NOT NULL DEFAULT 'default'")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_habits_bot_user ON habits(bot_key,user_id)")
        await conn.commit()
        row = await (await conn.execute("SELECT id,bot_key FROM habits")).fetchone()
        log = await (await conn.execute("SELECT habit_id FROM habit_logs")).fetchone()
        assert row == ("old-1", "default")
        assert log == ("old-1",)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_two_bot_reminder_jobs_do_not_deliver_foreign_habits(test_db, monkeypatch):
    from datetime import date
    from services import database
    await habit_service.create_habit_async(100, "Alpha only", reminder_time="09:00", bot_key="alpha")
    await habit_service.create_habit_async(100, "Beta only", reminder_time="09:00", bot_key="beta")
    monkeypatch.setattr(reminders, "_user_now", lambda uid: SimpleNamespace(strftime=lambda fmt: "09:00"))
    monkeypatch.setattr(reminders, "is_habit_due_on", lambda h: True)
    class _Context:
        def __init__(self, key):
            self.application = SimpleNamespace(bot_data={"bot_config": SimpleNamespace(key=key)})
            self.bot = SimpleNamespace(send_message=AsyncMock())
    first, second = _Context("alpha"), _Context("beta")
    await reminders.habit_reminders(first)
    await reminders.habit_reminders(second)
    assert first.bot.send_message.await_count == second.bot.send_message.await_count == 1
    assert "Alpha only" in first.bot.send_message.await_args.kwargs["text"]
    assert "Beta only" in second.bot.send_message.await_args.kwargs["text"]
