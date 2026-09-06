import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_habit_service_create_propagates_database_error(test_db):
    from services import habit_service

    with patch.object(habit_service, "execute", new=AsyncMock(side_effect=RuntimeError("db failure"))):
        with pytest.raises(RuntimeError, match="db failure"):
            await habit_service.create_habit_async("100", "Test")


@pytest.mark.asyncio
async def test_habit_service_mark_done_returns_false_on_integrity_error(test_db):
    from services import habit_service

    habit_id = await habit_service.create_habit_async("100", "Water")
    with patch.object(habit_service, "execute", new=AsyncMock(side_effect=habit_service.sqlite3.IntegrityError("duplicate"))):
        assert await habit_service.mark_done_async(habit_id, "100", "2026-09-07") is False


@pytest.mark.asyncio
async def test_habit_service_update_nonexistent_is_false(test_db):
    from services import habit_service

    assert await habit_service.update_habit_async("missing", title="New") is False


@pytest.mark.asyncio
async def test_habit_service_delete_nonexistent_is_false(test_db):
    from services import habit_service

    assert await habit_service.delete_habit_async("missing") is False


@pytest.mark.asyncio
async def test_habit_due_invalid_date_does_not_raise():
    from services.habit_service import is_habit_due_on

    assert is_habit_due_on({"start_date": "not-a-date", "repeat_type": "daily"}) is True


@pytest.mark.asyncio
async def test_reminder_habit_send_error_isolated_per_user():
    from services import reminders

    context = MagicMock()
    context.bot.send_message = AsyncMock(side_effect=RuntimeError("telegram unavailable"))
    with patch.object(reminders, "get_all_habit_user_ids_async", new=AsyncMock(return_value=["100", "101"])), \
         patch.object(reminders, "get_user_habits_async", new=AsyncMock(return_value=[{"id": "h1", "title": "Water", "repeat_type": "daily", "reminder_time": "12:00"}])), \
         patch.object(reminders, "_user_now", return_value=MagicMock(hour=12, minute=0, strftime=lambda fmt: "12:00")), \
         patch.object(reminders, "is_habit_due_on", return_value=True):
        await reminders.habit_reminders(context)

    assert context.bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_reminder_skips_invalid_user_id():
    from services import reminders

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch.object(reminders, "get_all_habit_user_ids_async", new=AsyncMock(return_value=["bad"])), \
         patch.object(reminders, "get_user_habits_async", new=AsyncMock()) as get_habits:
        await reminders.habit_reminders(context)

    get_habits.assert_not_awaited()
    context.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_morning_reminder_ignores_invalid_user_id():
    from services import reminders

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch.object(reminders, "get_all_user_ids_async", new=AsyncMock(return_value=["bad"])), \
         patch.object(reminders, "get_active_tasks_async", new=AsyncMock()) as get_tasks:
        await reminders.morning_today_tasks(context)

    get_tasks.assert_not_awaited()
    context.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_morning_reminder_continues_after_send_failure():
    from services import reminders

    context = MagicMock()
    context.bot.send_message = AsyncMock(side_effect=[RuntimeError("first"), None])
    tasks = [{"title": "Task", "priority": "high", "deadline": "2026-09-07", "status": "pending"}]
    with patch.object(reminders, "get_all_user_ids_async", new=AsyncMock(return_value=["100", "101"])), \
         patch.object(reminders, "_is_user_local_time", return_value=True), \
         patch.object(reminders, "_user_now", return_value=MagicMock(date=lambda: MagicMock(isoformat=lambda: "2026-09-07"))), \
         patch.object(reminders, "get_active_tasks_async", new=AsyncMock(return_value=tasks)):
        await reminders.morning_today_tasks(context)

    assert context.bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_midday_summary_continues_after_send_failure():
    from services import reminders

    context = MagicMock()
    context.bot.send_message = AsyncMock(side_effect=[RuntimeError("first"), None])
    task = {"title": "Task", "status": "pending", "deadline": "2026-09-07", "created_at": "2026-09-07 09:00"}
    now = MagicMock(date=lambda: __import__("datetime").date(2026, 9, 7), weekday=lambda: 0)
    with patch.object(reminders, "get_all_user_ids_async", new=AsyncMock(return_value=["100", "101"])), \
         patch.object(reminders, "_is_user_local_time", return_value=True), \
         patch.object(reminders, "_user_now", return_value=now), \
         patch.object(reminders, "get_all_user_tasks_async", new=AsyncMock(return_value=[task])):
        await reminders.midday_summary_and_weekly(context)

    assert context.bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_weekly_habit_report_skips_invalid_user_id():
    from services import reminders

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch.object(reminders, "get_all_habit_user_ids_async", new=AsyncMock(return_value=["bad"])), \
         patch.object(reminders, "get_user_habits_async", new=AsyncMock()) as get_habits:
        await reminders.weekly_habit_reports(context)

    get_habits.assert_not_awaited()
    context.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_deadline_reminders_delegates_to_morning_logic():
    from services import reminders

    with patch.object(reminders, "morning_today_tasks", new=AsyncMock()) as morning:
        context = MagicMock()
        await reminders.check_deadline_reminders(context)
        morning.assert_awaited_once_with(context)


def test_habit_reminder_times_handles_none_and_whitespace():
    from services.reminders import _habit_reminder_times

    assert _habit_reminder_times(None) == set()
    assert _habit_reminder_times("") == set()
    assert _habit_reminder_times(" 08:00, 11:00 , ,21:00 ") == {"08:00", "11:00", "21:00"}


@pytest.mark.asyncio
async def test_task_service_invalid_status_returns_false(test_db):
    from services import task_service

    assert await task_service.update_task_status_async("missing", "not-a-status") is False


@pytest.mark.asyncio
async def test_task_service_update_missing_task_returns_false(test_db):
    from services import task_service

    assert await task_service.update_task_async("missing", "100", title="Changed") is False


@pytest.mark.asyncio
async def test_task_service_search_empty_query_returns_empty(test_db):
    from services import task_service

    assert await task_service.search_tasks_async("100", "   ") == []


@pytest.mark.asyncio
async def test_task_service_create_rejects_invalid_priority(test_db):
    from services import task_service

    with pytest.raises(ValueError, match="invalid priority"):
        await task_service.create_task_async("100", "Task", "urgent", "", "", "")


@pytest.mark.asyncio
async def test_task_service_create_requires_user(test_db):
    from services import task_service

    with pytest.raises(ValueError, match="user_id is required"):
        await task_service.save_task_async(["t1", "", "Title"])


@pytest.mark.asyncio
async def test_task_service_assign_missing_task_returns_false(test_db):
    from services import task_service

    assert await task_service.assign_task_async("missing", {"user_id": "200"}, "100") is False


@pytest.mark.asyncio
async def test_task_service_add_comment_missing_task_returns_false(test_db):
    from services import task_service

    assert await task_service.add_task_comment_async("missing", {"id": "100", "full_name": "User"}, {"text": "Hi"}) is False
