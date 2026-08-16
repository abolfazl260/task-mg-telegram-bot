from datetime import date

from webapp.report_dashboard_service import _average_completion, _previous_period, resolve_period


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
