from datetime import date, datetime, timezone

from webapp.report_dashboard_service import (
    _average_completion,
    _previous_period,
    resolve_period,
    _productivity_metrics,
    _heatmap_data,
    gregorian_to_jalali,
)


def test_average_completion_ignores_incomplete_and_invalid_tasks():
    tasks = [
        {"status": "done", "created_at": "2026-08-01T00:00:00+00:00", "completed_at": "2026-08-03T12:00:00+00:00"},
        {"status": "done", "created_at": "2026-08-01T00:00:00+00:00", "completed_at": ""},
        {"status": "pending", "created_at": "2026-08-01T00:00:00+00:00", "completed_at": "2026-08-02T00:00:00+00:00"},
        {"status": "done", "created_at": "2026-08-03T00:00:00+00:00", "completed_at": "2026-08-02T00:00:00+00:00"},
    ]
    assert _average_completion(tasks) == 2.5


def test_custom_period_shifts_by_one_calendar_month_for_comparison():
    assert _previous_period(date(2026, 8, 10), date(2026, 8, 19)) == (date(2026, 7, 10), date(2026, 7, 19))


def test_custom_period_normalizes_reversed_dates():
    assert resolve_period("custom", "2026-08-20", "2026-08-10") == (date(2026, 8, 10), date(2026, 8, 20))


def test_gregorian_to_jalali_conversion():
    assert gregorian_to_jalali(2026, 9, 5) == (1405, 6, 14)
    assert gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)


def test_productivity_metrics_lead_time_and_on_time_rates():
    now = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
    tasks = [
        # Completed on time (completed 2026-08-03 <= deadline 2026-08-04)
        {"status": "done", "created_at": "2026-08-01T00:00:00Z", "completed_at": "2026-08-03T00:00:00Z", "deadline": "2026-08-04"},
        # Completed late (completed 2026-08-06 > deadline 2026-08-05)
        {"status": "done", "created_at": "2026-08-02T00:00:00Z", "completed_at": "2026-08-06T00:00:00Z", "deadline": "2026-08-05"},
        # Open and currently overdue (deadline 2026-08-08 < today 2026-08-10)
        {"status": "in_progress", "created_at": "2026-08-04T00:00:00Z", "deadline": "2026-08-08"},
        # Open and on track (deadline 2026-08-12 >= today 2026-08-10)
        {"status": "pending", "created_at": "2026-08-05T00:00:00Z", "deadline": "2026-08-12"},
    ]
    metrics = _productivity_metrics(tasks, now=now)
    assert metrics["completed_with_deadline"] == 2
    assert metrics["completed_on_time"] == 1
    assert metrics["completed_late"] == 1
    assert metrics["on_time_rate"] == 50
    assert metrics["overdue_rate"] == 50
    assert metrics["open_overdue"] == 1
    assert metrics["open_on_track"] == 1
    assert metrics["lead_time_days"] == 3.0
    assert metrics["lead_time_hours"] == 72.0


def test_heatmap_data_jalali_calendar_and_levels():
    tasks = [
        {"created_at": "2026-08-01T10:00:00Z", "status": "done", "completed_at": "2026-08-01T15:00:00Z"},
        {"created_at": "2026-08-01T12:00:00Z", "status": "pending"},
        {"created_at": "2026-08-02T08:00:00Z", "status": "done", "completed_at": "2026-08-02T18:00:00Z"},
    ]
    data = _heatmap_data(tasks, date(2026, 8, 1), date(2026, 8, 3))
    assert data["section"] == "heatmap"
    assert len(data["days"]) == 3
    assert data["days"][0]["activity"] == 3
    assert data["days"][0]["jalali_date"] == "1405/05/10"
    assert data["days"][0]["weekday_name"] == "شنبه"
    assert data["max_count"] == 3
    assert len(data["busiest_days"]) > 0
    assert data["busiest_days"][0]["date"] == "2026-08-01"
