"""Issue #218: direct habit-service and forged Telegram callback authorization tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from handlers import habits as habit_handlers
from services import habit_service
from services.database import execute, fetch_one


@pytest.mark.asyncio
async def test_owner_only_habit_access_read_update_delete_and_logs(test_db):
    owned = await habit_service.create_habit_async("100", "Owner habit")
    other = await habit_service.create_habit_async("200", "Other habit")

    assert (await habit_service.get_habit_async(owned, "100"))["id"] == owned
    assert await habit_service.get_habit_async(owned, "200") is None
    assert await habit_service.get_habit_async("missing", "100") is None

    assert await habit_service.update_habit_async(owned, "200", title="Hacked") is False
    assert (await habit_service.get_habit_async(owned, "100"))["title"] == "Owner habit"
    assert await habit_service.delete_habit_async(owned, "200") is False
    assert await habit_service.get_habit_async(owned, "100") is not None

    assert await habit_service.mark_done_async(owned, "100", "2026-10-10") is True
    assert await habit_service.mark_done_async(owned, "200", "2026-10-11") is False
    assert await habit_service.mark_done_async("missing", "100", "2026-10-11") is False
    assert await habit_service.get_logs_async(user_id="200", habit_id=owned) == []
    assert len(await habit_service.get_logs_async(user_id="100", habit_id=owned)) == 1
    assert await habit_service.get_logs_async(user_id="100", habit_id=other) == []

    # Legacy incorrect cross-user completion rows must not contaminate owner
    # statistics, and cannot be made visible through unscoped habit-ID reads.
    await execute(
        "INSERT INTO habit_logs(habit_id,user_id,done_date,done_at) VALUES(?,?,?,?)",
        (owned, "200", "2026-10-09", "2026-10-09T13:00:00Z"),
    )
    assert len(await habit_service.get_logs_async(user_id="100", habit_id=owned)) == 1
    assert await habit_service.get_logs_async(user_id="200", habit_id=owned) == []
    stats = await habit_service.stats_for_habit_async({"id": owned}, "100")
    assert stats["total"] == 1
    with pytest.raises(PermissionError, match="habit_access_denied"):
        await habit_service.stats_for_habit_async({"id": owned}, "200")
    with pytest.raises(PermissionError, match="habit_access_denied"):
        await habit_service.stats_for_habit_async({"id": "missing"}, "100")

    assert await habit_service.update_habit_async(owned, "100", title="Changed") is True
    assert (await habit_service.get_habit_async(owned, "100"))["title"] == "Changed"
    assert await habit_service.delete_habit_async(owned, "100") is True
    assert await habit_service.get_habit_async(owned, "100") is None
    assert await fetch_one("habits", "id=?", (other,)) is not None


@pytest.mark.asyncio
async def test_unowned_completion_does_not_create_user_or_record(test_db):
    owned = await habit_service.create_habit_async("100", "No foreign completions")
    assert not await habit_service.mark_done_async(owned, "999", "2026-10-10")
    assert await fetch_one("users", "user_id=?", ("999",)) is None
    assert await habit_service.get_logs_async("100", owned) == []


def _callback_update(data, actor=200):
    response = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(data=data, message=response, answer=AsyncMock())
    return SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=actor))


@pytest.mark.asyncio
@pytest.mark.parametrize("callback", [
    "habit_done_foreign",
    "habit_rempick_foreign",
    "habit_remtime_foreign_09:00",
    "habit_edit_foreign",
])
async def test_forged_callback_does_not_access_or_mutate_habits(monkeypatch, callback):
    get = Mock(return_value=None)
    mark = Mock(return_value=False)
    update = Mock(return_value=False)
    stats = Mock(side_effect=AssertionError("should not compute unauthorized statistics"))
    monkeypatch.setattr(habit_handlers, "get_habit", get)
    monkeypatch.setattr(habit_handlers, "mark_done", mark)
    monkeypatch.setattr(habit_handlers, "update_habit", update)
    monkeypatch.setattr(habit_handlers, "stats_for_habit", stats)

    user_data = {}
    context = SimpleNamespace(user_data=user_data)
    message = _callback_update(callback)
    await habit_handlers.handle_habit_callback(message, context)

    assert message.callback_query.message.reply_text.await_count == 1
    assert "دسترسی" in message.callback_query.message.reply_text.await_args.args[0] or (
        "قبلاً" in message.callback_query.message.reply_text.await_args.args[0]
    )
    assert "habit_edit_id" not in user_data
    stats.assert_not_called()
    if callback.startswith("habit_done_"):
        mark.assert_called_once_with("foreign", 200)
    elif callback.startswith("habit_remtime_"):
        update.assert_called_once_with("foreign", 200, reminder_time="09:00")
    else:
        get.assert_called_once_with("foreign", 200)


@pytest.mark.asyncio
async def test_stale_edit_flow_rechecks_identity_at_commit(monkeypatch):
    update_habit = Mock(return_value=False)
    monkeypatch.setattr(habit_handlers, "update_habit", update_habit)
    message = SimpleNamespace(
        text="Unauthorized title",
        reply_text=AsyncMock(),
    )
    incoming = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=200),
    )
    context = SimpleNamespace(user_data={"habit_step": "edit_title", "habit_edit_id": "foreign"})
    assert await habit_handlers.handle_habit_text(incoming, context) is True
    update_habit.assert_called_once_with("foreign", 200, title="Unauthorized title")
    assert "habit_edit_id" not in context.user_data
    assert "دسترسی" in message.reply_text.await_args.args[0]
