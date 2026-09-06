import pytest
from types import SimpleNamespace
from datetime import date

from services import reminders


class FakeBot:
    def __init__(self):
        self.messages = []
        self.fail = False

    async def send_message(self, **kwargs):
        if self.fail:
            raise RuntimeError("telegram unavailable")
        self.messages.append(kwargs)
        return SimpleNamespace(**kwargs)


@pytest.fixture
def context():
    return SimpleNamespace(bot=FakeBot())


def test_priority_emoji_has_all_supported_priorities():
    assert reminders._priority_emoji("high") == "🔴"
    assert reminders._priority_emoji("medium") == "🟠"
    assert reminders._priority_emoji("low") == "🟢"
    assert reminders._priority_emoji("unknown") == "🟢"
    assert reminders._priority_emoji(None) == "🟢"


def test_habit_reminder_times_parses_multiple_values_and_ignores_empty_items():
    assert reminders._habit_reminder_times("08:00, 11:30,,21:00 ") == {"08:00", "11:30", "21:00"}
    assert reminders._habit_reminder_times("") == set()
    assert reminders._habit_reminder_times(None) == set()


def test_is_user_local_time_matches_exact_hour_and_minute(monkeypatch):
    class FakeNow:
        hour = 7
        minute = 0

    monkeypatch.setattr(reminders, "_user_now", lambda user_id: FakeNow())
    assert reminders._is_user_local_time(10, 7, 0) is True
    assert reminders._is_user_local_time(10, 7, 1) is False
    assert reminders._is_user_local_time(10, 8, 0) is False


@pytest.mark.asyncio
async def test_morning_today_tasks_sends_today_and_overdue_tasks(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda user_id, hour, minute: True)
    monkeypatch.setattr(
        reminders,
        "_user_now",
        lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 7)),
    )
    monkeypatch.setattr(
        reminders,
        "get_active_tasks_async",
        lambda user_id: _async_value([
            {"title": "Medium", "priority": "medium", "deadline": "2026-09-07"},
            {"title": "High", "priority": "high", "deadline": "2026-09-07"},
            {"title": "Old", "priority": "low", "deadline": "2026-09-06"},
        ]),
    )

    await reminders.morning_today_tasks(context)

    assert len(context.bot.messages) == 1
    message = context.bot.messages[0]
    assert message["chat_id"] == 101
    assert "☀️ صبح بخیر" in message["text"]
    assert "تسک‌های امروز (2)" in message["text"]
    assert "High" in message["text"]
    assert "Medium" in message["text"]
    assert "عقب‌افتاده (1)" in message["text"]
    assert "Old" in message["text"]
    assert message["text"].index("High") < message["text"].index("Medium")


@pytest.mark.asyncio
async def test_morning_today_tasks_skips_users_when_not_local_seven(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda user_id, hour, minute: False)
    await reminders.morning_today_tasks(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_morning_today_tasks_skips_invalid_user_ids(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["bad", "", None]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    await reminders.morning_today_tasks(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_morning_today_tasks_does_not_send_when_no_due_or_overdue_tasks(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 7)))
    monkeypatch.setattr(reminders, "get_active_tasks_async", lambda user_id: _async_value([]))

    await reminders.morning_today_tasks(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_morning_today_tasks_limits_overdue_items_to_eight(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 7)))
    tasks = [
        {"title": f"Old {i}", "priority": "low", "deadline": "2026-09-06"}
        for i in range(10)
    ]
    monkeypatch.setattr(reminders, "get_active_tasks_async", lambda user_id: _async_value(tasks))

    await reminders.morning_today_tasks(context)

    text = context.bot.messages[0]["text"]
    assert "عقب‌افتاده (10)" in text
    assert "Old 0" in text and "Old 7" in text
    assert "Old 8" not in text and "Old 9" not in text
    assert "... و 2 مورد دیگر" in text


@pytest.mark.asyncio
async def test_morning_today_tasks_continues_when_telegram_send_fails(context, monkeypatch):
    context.bot.fail = True
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 7)))
    monkeypatch.setattr(reminders, "get_active_tasks_async", lambda user_id: _async_value([
        {"title": "Task", "priority": "low", "deadline": "2026-09-07"}
    ]))

    await reminders.morning_today_tasks(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_midday_summary_skips_non_eleven_users_and_empty_task_lists(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101", "102"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda user_id, hour, minute: user_id == 101)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 7)))
    monkeypatch.setattr(reminders, "get_all_user_tasks_async", lambda user_id: _async_value([]))

    await reminders.midday_summary_and_weekly(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_midday_summary_counts_done_due_active_and_weekly_activity(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 9)))
    monkeypatch.setattr(
        reminders,
        "get_all_user_tasks_async",
        lambda user_id: _async_value([
            {"title": "Done today", "status": "done", "completed_at": "2026-09-09 10:00", "created_at": "2026-09-08 09:00", "deadline": ""},
            {"title": "Due today", "status": "pending", "deadline": "2026-09-09", "created_at": "2026-09-08 09:00"},
            {"title": "Active other", "status": "in_progress", "deadline": "2026-09-20", "created_at": "2026-09-09 09:00"},
            {"title": "Done this week", "status": "done", "completed_at": "2026-09-08 10:00", "created_at": "2026-09-08 09:00", "deadline": ""},
            {"title": "Old done", "status": "done", "completed_at": "2026-08-30 10:00", "created_at": "2026-08-30 09:00", "deadline": ""},
        ]),
    )

    await reminders.midday_summary_and_weekly(context)

    text = context.bot.messages[0]["text"]
    assert "انجام‌شده امروز: 1" in text
    assert "Done today" in text
    assert "باقی‌مانده امروز: 1" in text
    assert "کل فعال: 2" in text
    assert "ایجادشده این هفته: 4" in text
    assert "انجام‌شده این هفته: 2" in text


@pytest.mark.asyncio
async def test_midday_summary_handles_malformed_dates_without_failing(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 9)))
    monkeypatch.setattr(reminders, "get_all_user_tasks_async", lambda user_id: _async_value([
        {"title": "Task", "status": "pending", "created_at": "not-a-date", "deadline": ""},
        {"title": "Done", "status": "done", "completed_at": "bad", "created_at": "bad"},
    ]))

    await reminders.midday_summary_and_weekly(context)
    assert len(context.bot.messages) == 1
    assert "کل فعال: 1" in context.bot.messages[0]["text"]


@pytest.mark.asyncio
async def test_midday_summary_continues_when_telegram_send_fails(context, monkeypatch):
    context.bot.fail = True
    monkeypatch.setattr(reminders, "get_all_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_is_user_local_time", lambda *args: True)
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(date=lambda: date(2026, 9, 9)))
    monkeypatch.setattr(reminders, "get_all_user_tasks_async", lambda user_id: _async_value([
        {"title": "Task", "status": "pending", "deadline": "2026-09-09", "created_at": "2026-09-09 09:00"}
    ]))

    await reminders.midday_summary_and_weekly(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_check_deadline_reminders_delegates_to_morning_task_reminder(context, monkeypatch):
    called = []

    async def fake_morning(ctx):
        called.append(ctx)

    monkeypatch.setattr(reminders, "morning_today_tasks", fake_morning)
    await reminders.check_deadline_reminders(context)
    assert called == [context]


@pytest.mark.asyncio
async def test_habit_reminders_sends_only_active_due_habits_with_matching_time(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(strftime=lambda fmt: "09:00"))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda user_id, active_only=False: _async_value([
        {"id": "h1", "title": "Drink water", "reminder_time": "09:00", "repeat_type": "daily", "start_date": "2026-01-01"},
        {"id": "h2", "title": "Read", "reminder_time": "10:00", "repeat_type": "daily", "start_date": "2026-01-01"},
        {"id": "h3", "title": "Inactive", "reminder_time": "09:00", "repeat_type": "daily", "start_date": "2026-01-01"},
    ]))
    monkeypatch.setattr(reminders, "is_habit_due_on", lambda habit: habit["id"] != "h3")

    await reminders.habit_reminders(context)

    assert len(context.bot.messages) == 1
    message = context.bot.messages[0]
    assert message["chat_id"] == 101
    assert "Drink water" in message["text"]
    keyboard = message["reply_markup"]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "habit_done_h1" in callbacks
    assert "habit_menu" in callbacks


@pytest.mark.asyncio
async def test_habit_reminders_does_not_send_when_no_time_matches(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(strftime=lambda fmt: "09:01"))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value([
        {"id": "h1", "title": "Habit", "reminder_time": "09:00", "repeat_type": "daily", "start_date": "2026-01-01"}
    ]))
    monkeypatch.setattr(reminders, "is_habit_due_on", lambda habit: True)

    await reminders.habit_reminders(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_habit_reminders_skips_invalid_user_ids_and_continues(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["bad", "101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(strftime=lambda fmt: "09:00"))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value([
        {"id": "h1", "title": "Habit", "reminder_time": "09:00"}
    ]))
    monkeypatch.setattr(reminders, "is_habit_due_on", lambda habit: True)

    await reminders.habit_reminders(context)
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["chat_id"] == 101


@pytest.mark.asyncio
async def test_habit_reminders_continues_when_telegram_send_fails(context, monkeypatch):
    context.bot.fail = True
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(strftime=lambda fmt: "09:00"))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value([
        {"id": "h1", "title": "Habit", "reminder_time": "09:00"}
    ]))
    monkeypatch.setattr(reminders, "is_habit_due_on", lambda habit: True)

    await reminders.habit_reminders(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_weekly_habit_reports_runs_only_friday_at_18_and_builds_report(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(
        weekday=lambda: 4,
        hour=18,
        minute=0,
        date=lambda: date(2026, 9, 11),
    ))
    habits = [
        {"id": "h1", "title": "Water"},
        {"id": "h2", "title": "Reading"},
    ]
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value(habits))
    monkeypatch.setattr(reminders, "get_logs_async", lambda **kwargs: _async_value([
        {"habit_id": "h1", "done_date": "2026-09-07"},
        {"habit_id": "h1", "done_date": "2026-09-08"},
        {"habit_id": "h1", "done_date": "2026-09-09"},
        {"habit_id": "h2", "done_date": "2026-09-07"},
    ]))
    monkeypatch.setattr(reminders, "stats_for_habit_async", lambda habit: _async_value(
        {"best": 5 if habit["id"] == "h2" else 3}
    ))

    await reminders.weekly_habit_reports(context)

    assert len(context.bot.messages) == 1
    text = context.bot.messages[0]["text"]
    assert "📊 گزارش هفتگی عادت‌ها" in text
    assert "انجام شده:\n4 بار" in text
    assert "انجام نشده:\n10 بار" in text
    assert "Water" in text
    assert "3 روز از 7 روز" in text
    assert "Reading" in text
    assert "5 روز" in text


@pytest.mark.asyncio
async def test_weekly_habit_reports_skips_when_not_friday_or_not_six_pm(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value([
        {"id": "h1", "title": "Habit"}
    ]))

    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(
        weekday=lambda: 3,
        hour=18,
        minute=0,
        date=lambda: date(2026, 9, 10),
    ))
    await reminders.weekly_habit_reports(context)
    assert context.bot.messages == []

    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(
        weekday=lambda: 4,
        hour=17,
        minute=59,
        date=lambda: date(2026, 9, 11),
    ))
    await reminders.weekly_habit_reports(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_weekly_habit_reports_skips_users_without_active_habits(context, monkeypatch):
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(
        weekday=lambda: 4,
        hour=18,
        minute=0,
        date=lambda: date(2026, 9, 11),
    ))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value([]))
    await reminders.weekly_habit_reports(context)
    assert context.bot.messages == []


@pytest.mark.asyncio
async def test_weekly_habit_reports_continues_when_telegram_send_fails(context, monkeypatch):
    context.bot.fail = True
    monkeypatch.setattr(reminders, "get_all_habit_user_ids_async", lambda: _async_value(["101"]))
    monkeypatch.setattr(reminders, "_user_now", lambda user_id: SimpleNamespace(
        weekday=lambda: 4,
        hour=18,
        minute=0,
        date=lambda: date(2026, 9, 11),
    ))
    monkeypatch.setattr(reminders, "get_user_habits_async", lambda *args, **kwargs: _async_value([
        {"id": "h1", "title": "Habit"}
    ]))
    monkeypatch.setattr(reminders, "get_logs_async", lambda **kwargs: _async_value([]))
    monkeypatch.setattr(reminders, "stats_for_habit_async", lambda habit: _async_value({"best": 0}))

    await reminders.weekly_habit_reports(context)
    assert context.bot.messages == []


async def _async_value(value):
    return value
