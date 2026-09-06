import pytest
from datetime import date, timedelta

from services import habit_service


@pytest.mark.asyncio
async def test_create_and_get_habit_persists_all_fields(test_db):
    habit_id = await habit_service.create_habit_async(
        100,
        "Study Python",
        category="Learning",
        description="Read and practice",
        repeat_type="daily",
        target="30 minutes",
        reminder_time="09:00,18:00",
        start_date="2026-09-01",
    )

    habit = await habit_service.get_habit_async(habit_id)
    assert habit is not None
    assert habit["id"] == habit_id
    assert habit["user_id"] == "100"
    assert habit["title"] == "Study Python"
    assert habit["category"] == "Learning"
    assert habit["description"] == "Read and practice"
    assert habit["repeat_type"] == "daily"
    assert habit["target"] == "30 minutes"
    assert habit["reminder_time"] == "09:00,18:00"
    assert habit["start_date"] == "2026-09-01"
    assert habit["active"] in (1, "1")
    assert habit["created_at"]


@pytest.mark.asyncio
async def test_create_habit_applies_defaults_and_ensures_user(test_db):
    habit_id = await habit_service.create_habit_async(200, "Drink water")
    habit = await habit_service.get_habit_async(habit_id)
    assert habit["category"] == ""
    assert habit["description"] == ""
    assert habit["repeat_type"] == "daily"
    assert habit["target"] == ""
    assert habit["reminder_time"] == ""
    assert habit["start_date"] == date.today().isoformat()

    from services.database import fetch_one
    user = await fetch_one("users", "user_id=?", ("200",))
    assert user is not None
    assert user["date_format"] == "jalali"


@pytest.mark.asyncio
async def test_user_habits_are_isolated_and_active_filter_works(test_db):
    first = await habit_service.create_habit_async(100, "A")
    second = await habit_service.create_habit_async(100, "B")
    other = await habit_service.create_habit_async(200, "Other")
    assert await habit_service.update_habit_async(second, active=0)

    user_100 = await habit_service.get_user_habits_async(100)
    assert {h["id"] for h in user_100} == {first, second}
    assert {h["id"] for h in await habit_service.get_user_habits_async(100, active_only=True)} == {first}
    assert [h["id"] for h in await habit_service.get_user_habits_async(200)] == [other]


@pytest.mark.asyncio
async def test_update_habit_changes_only_allowed_fields(test_db):
    habit_id = await habit_service.create_habit_async(100, "Original", category="Old")
    assert await habit_service.update_habit_async(
        habit_id,
        title="Updated",
        category="New",
        description="Desc",
        repeat_type="weekly",
        target="5",
        reminder_time="10:00",
        start_date="2026-09-07",
        active=0,
        user_id="attacker",
        id="must-not-change",
    )
    habit = await habit_service.get_habit_async(habit_id)
    assert habit["title"] == "Updated"
    assert habit["category"] == "New"
    assert habit["description"] == "Desc"
    assert habit["repeat_type"] == "weekly"
    assert habit["target"] == "5"
    assert habit["reminder_time"] == "10:00"
    assert habit["start_date"] == "2026-09-07"
    assert habit["active"] in (0, "0")
    assert habit["id"] == habit_id
    assert habit["user_id"] == "100"


@pytest.mark.asyncio
async def test_update_nonexistent_or_empty_changes_returns_false(test_db):
    assert not await habit_service.update_habit_async("missing", title="X")
    habit_id = await habit_service.create_habit_async(100, "A")
    assert not await habit_service.update_habit_async(habit_id, unknown="value")


@pytest.mark.asyncio
async def test_delete_habit_is_idempotent_for_missing_id(test_db):
    habit_id = await habit_service.create_habit_async(100, "Delete me")
    assert await habit_service.delete_habit_async(habit_id)
    assert await habit_service.get_habit_async(habit_id) is None
    assert not await habit_service.delete_habit_async(habit_id)


@pytest.mark.asyncio
async def test_mark_done_creates_log_and_duplicate_same_day_is_rejected(test_db):
    habit_id = await habit_service.create_habit_async(100, "Exercise")
    assert await habit_service.mark_done_async(habit_id, 100, "2026-09-07")
    assert not await habit_service.mark_done_async(habit_id, 100, "2026-09-07")

    logs = await habit_service.get_logs_async(user_id=100, habit_id=habit_id)
    assert len(logs) == 1
    assert logs[0]["habit_id"] == habit_id
    assert logs[0]["user_id"] == "100"
    assert logs[0]["done_date"] == "2026-09-07"
    assert logs[0]["done_at"]


@pytest.mark.asyncio
async def test_logs_can_be_filtered_by_user_and_habit(test_db):
    h1 = await habit_service.create_habit_async(100, "A")
    h2 = await habit_service.create_habit_async(100, "B")
    h3 = await habit_service.create_habit_async(200, "C")
    await habit_service.mark_done_async(h1, 100, "2026-09-01")
    await habit_service.mark_done_async(h2, 100, "2026-09-01")
    await habit_service.mark_done_async(h3, 200, "2026-09-01")

    assert len(await habit_service.get_logs_async(user_id=100)) == 2
    assert [x["habit_id"] for x in await habit_service.get_logs_async(habit_id=h1)] == [h1]
    assert len(await habit_service.get_logs_async(user_id=100, habit_id=h2)) == 1
    assert len(await habit_service.get_logs_async()) == 3


@pytest.mark.asyncio
async def test_mark_done_creates_user_when_needed(test_db):
    habit_id = await habit_service.create_habit_async(100, "A")
    assert await habit_service.mark_done_async(habit_id, 300, "2026-09-01")
    logs = await habit_service.get_logs_async(user_id=300)
    assert len(logs) == 1
    assert logs[0]["habit_id"] == habit_id


@pytest.mark.parametrize(
    "repeat_type,start,day,expected",
    [
        ("daily", "2026-09-07", "2026-09-07", True),
        ("daily", "2026-09-07", "2026-09-10", True),
        ("daily", "2026-09-07", "2026-09-06", False),
        ("weekly", "2026-09-07", "2026-09-07", True),
        ("weekly", "2026-09-07", "2026-09-14", True),
        ("weekly", "2026-09-07", "2026-09-08", False),
        ("monthly", "2026-09-07", "2026-10-07", True),
        ("monthly", "2026-09-07", "2026-10-08", False),
    ],
)
def test_is_habit_due_on_repeat_rules(repeat_type, start, day, expected):
    habit = {"repeat_type": repeat_type, "start_date": start}
    assert habit_service.is_habit_due_on(habit, date.fromisoformat(day)) is expected


def test_is_habit_due_on_handles_invalid_start_date_without_crashing():
    habit = {"repeat_type": "daily", "start_date": "not-a-date"}
    assert habit_service.is_habit_due_on(habit, date(2026, 9, 7)) is True


def test_is_habit_due_on_defaults_to_daily():
    assert habit_service.is_habit_due_on({"start_date": "2026-09-01"}, date(2026, 9, 5)) is True


@pytest.mark.asyncio
async def test_stats_for_habit_empty_state(test_db):
    habit_id = await habit_service.create_habit_async(100, "A")
    stats = await habit_service.stats_for_habit_async({"id": habit_id})
    assert stats == {"current": 0, "best": 0, "total": 0, "last": "—"}


@pytest.mark.asyncio
async def test_stats_calculates_total_best_current_and_last(test_db, monkeypatch):
    habit_id = await habit_service.create_habit_async(100, "A")
    today = date(2026, 9, 7)
    monkeypatch.setattr(habit_service, "date", type("FakeDate", (), {"today": staticmethod(lambda: today)}))
    for day in ["2026-09-03", "2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07"]:
        assert await habit_service.mark_done_async(habit_id, 100, day)
    for day in ["2026-08-20", "2026-08-21"]:
        assert await habit_service.mark_done_async(habit_id, 100, day)

    stats = await habit_service.stats_for_habit_async({"id": habit_id})
    assert stats["current"] == 5
    assert stats["best"] == 5
    assert stats["total"] == 7
    assert stats["last"] == "2026-09-07"


@pytest.mark.asyncio
async def test_stats_current_streak_starts_from_yesterday_when_today_missing(test_db, monkeypatch):
    habit_id = await habit_service.create_habit_async(100, "A")
    today = date(2026, 9, 7)
    monkeypatch.setattr(habit_service, "date", type("FakeDate", (), {"today": staticmethod(lambda: today)}))
    for day in ["2026-09-05", "2026-09-06"]:
        assert await habit_service.mark_done_async(habit_id, 100, day)

    stats = await habit_service.stats_for_habit_async({"id": habit_id})
    assert stats["current"] == 2
    assert stats["best"] == 2
    assert stats["total"] == 2


@pytest.mark.asyncio
async def test_stats_best_streak_is_not_broken_by_later_gap(test_db, monkeypatch):
    habit_id = await habit_service.create_habit_async(100, "A")
    today = date(2026, 9, 20)
    monkeypatch.setattr(habit_service, "date", type("FakeDate", (), {"today": staticmethod(lambda: today)}))
    for day in ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-10"]:
        assert await habit_service.mark_done_async(habit_id, 100, day)

    stats = await habit_service.stats_for_habit_async({"id": habit_id})
    assert stats["current"] == 0
    assert stats["best"] == 3
    assert stats["total"] == 4
    assert stats["last"] == "2026-09-10"


def test_templates_are_complete_and_unique():
    keys = [t["key"] for t in habit_service.TEMPLATES]
    assert keys
    assert len(keys) == len(set(keys))
    required = {"key", "title", "repeat_type", "target", "target_value", "target_unit", "kind"}
    for template in habit_service.TEMPLATES:
        assert required.issubset(template)
        assert template["key"]
        assert template["title"]
        assert template["repeat_type"] in {"daily", "weekly", "monthly"}
        assert template["target_value"] is not None
        assert template["target_unit"]


@pytest.mark.asyncio
async def test_get_all_habit_user_ids_returns_unique_sorted_users(test_db):
    await habit_service.create_habit_async(300, "C")
    await habit_service.create_habit_async(100, "A")
    await habit_service.create_habit_async(300, "C2")
    await habit_service.create_habit_async(200, "B")
    assert await habit_service.get_all_habit_user_ids_async() == ["100", "200", "300"]
