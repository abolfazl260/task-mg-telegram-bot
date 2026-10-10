"""Multi-profile Habit isolation, legacy migration, and scheduler regressions (#219)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import habit_service, reminders
from services.database import CORE_SCHEMA, fetch_one, migrate_core_schema


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
        current = "id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, bot_key TEXT NOT NULL DEFAULT 'default', title TEXT NOT NULL"
        legacy = "id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, title TEXT NOT NULL"
        assert current in CORE_SCHEMA
        await conn.executescript(CORE_SCHEMA.replace(current, legacy))
        await conn.execute("INSERT INTO users(user_id) VALUES ('100')")
        await conn.execute("INSERT INTO habits(id,user_id,title) VALUES ('old-1','100','Preserve me')")
        await conn.execute("INSERT INTO habit_logs(habit_id,user_id,done_date) VALUES ('old-1','100','2026-09-01')")
        await migrate_core_schema(conn)
        await migrate_core_schema(conn)  # repeatable migration
        row = await (await conn.execute("SELECT id,bot_key FROM habits")).fetchone()
        log = await (await conn.execute("SELECT habit_id FROM habit_logs")).fetchone()
        assert row == ("old-1", "default")
        assert log == ("old-1",)
    finally:
        await conn.close()

@pytest.mark.asyncio
async def test_two_bot_reminder_jobs_do_not_deliver_foreign_habits(test_db, monkeypatch):
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
