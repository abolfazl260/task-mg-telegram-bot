from datetime import date, datetime, timezone
from pathlib import Path

from webapp import report_dashboard_service as dashboard_service
from webapp.report_dashboard_service import (
    _average_completion,
    _previous_period,
    resolve_period,
    _productivity_metrics,
    _heatmap_data,
    _jalali_date,
    _row,
    dashboard_report,
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


def test_jalali_date_formats_iso_deadline_without_approximation():
    assert _jalali_date("2026-08-04") == "1405/05/13"
    assert _jalali_date("2026-03-21T09:30:00+00:00") == "1405/01/01"
    assert _jalali_date("") == ""
    assert _jalali_date("not-a-date") == ""


def test_report_row_includes_precomputed_jalali_deadline():
    row = _row({
        "id": "task-1",
        "title": "نمونه",
        "status": "pending",
        "priority": "medium",
        "deadline": "2026-08-04",
    })
    assert row["deadline"] == "2026-08-04"
    assert row["deadline_jalali"] == "1405/05/13"


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



def test_dashboard_trend_reuses_current_search_and_filters_for_previous_period(monkeypatch):
    current_tasks = [{
        "id": "current-high",
        "title": "needle current",
        "status": "pending",
        "priority": "high",
        "created_at": "2026-08-10T00:00:00Z",
    }]
    previous_tasks = [
        {
            "id": "previous-high-1",
            "title": "needle previous 1",
            "status": "pending",
            "priority": "high",
            "created_at": "2026-07-10T00:00:00Z",
        },
        {
            "id": "previous-high-2",
            "title": "needle previous 2",
            "status": "pending",
            "priority": "high",
            "created_at": "2026-07-11T00:00:00Z",
        },
    ]
    calls = []

    monkeypatch.setattr(dashboard_service, "_access", lambda token: {"bot_key": "bot", "user_id": "1"})

    def fake_query(access, start, end, search="", filters=None):
        calls.append({"start": start, "end": end, "search": search, "filters": dict(filters or {})})
        return current_tasks if start.month == 8 else previous_tasks

    monkeypatch.setattr(dashboard_service, "_query_tasks", fake_query)

    search = '{"q":"needle","priority":"high","sort":"newest"}'
    result = dashboard_report(
        "token",
        period="custom",
        start_value="2026-08-01",
        end_value="2026-08-31",
        search=search,
    )

    previous_call = calls[-1]
    assert previous_call["start"] == date(2026, 7, 1)
    assert previous_call["search"] == "needle"
    assert previous_call["filters"]["priority"] == "high"
    assert result["summary"]["total"] == 1
    assert result["summary"]["total_change"]["direction"] == "down"
    assert result["summary"]["total_change"]["percentage"] == 50


def test_dashboard_tasks_page_size_zero_returns_all_filtered_rows(monkeypatch):
    tasks = [
        {
            "id": f"task-{index}",
            "title": f"Task {index}",
            "status": "pending",
            "priority": "medium",
            "created_at": f"2026-08-{index + 1:02d}T00:00:00Z",
        }
        for index in range(30)
    ]

    monkeypatch.setattr(dashboard_service, "_access", lambda token: {"bot_key": "bot", "user_id": "1"})
    monkeypatch.setattr(
        dashboard_service,
        "_query_tasks",
        lambda access, start, end, search="", filters=None: tasks,
    )

    result = dashboard_report(
        "token",
        section="tasks",
        page=1,
        page_size=0,
        period="custom",
        start_value="2026-08-01",
        end_value="2026-08-31",
    )

    assert result["total"] == 30
    assert len(result["rows"]) == 30
    assert result["page"] == 1
    assert result["pages"] == 1
    assert result["page_size"] == 30


def test_clear_filters_ui_resets_controls_and_refreshes_filter_card():
    source = (Path(__file__).parents[1] / "webapp" / "report_dashboard.js").read_text(encoding="utf-8")
    clear_start = source.index("document.getElementById('clearReportFilters')")
    clear_end = source.index("['filterStart', 'filterEnd']", clear_start)
    clear_handler = source[clear_start:clear_end]

    assert "state.period = 'month'" in clear_handler
    assert "syncFilterControls();" in clear_handler
    assert "existingFilters.outerHTML = filterCard(data.filter_options || {});" in source
