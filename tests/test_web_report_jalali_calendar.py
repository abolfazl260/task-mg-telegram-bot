"""Issue #228: real due-date calendar and solar-month navigation regressions."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import jdatetime
import pytest

from webapp import report_dashboard_service as dashboard
from webapp import reports


@pytest.fixture
def core_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY, user_id TEXT, bot_key TEXT, workspace_id TEXT,
            team_id TEXT, title TEXT, status TEXT, priority TEXT,
            created_at TEXT, completed_at TEXT, deadline TEXT, category TEXT,
            assignee_id TEXT, assignee_name TEXT, assignee_username TEXT, tags TEXT
        );
        CREATE TABLE team_members(team_id TEXT, user_id TEXT, role TEXT);
        """
    )

    def task(identifier, created="2025-01-01", due="2026-10-10", *, user="42",
             team=None, workspace=None, status="pending", bot="default"):
        conn.execute(
            "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (identifier, user, bot, workspace, team, identifier, status, "medium",
             created, "", due, "work", "", "", "", ""),
        )

    for index in range(40):
        task(f"old-{index:02d}")
    task("today-created", created="2026-10-03", due="2026-10-11", status="in_progress")
    task("authorized-team", user="99", team="shared", bot="clinic")
    task("unscheduled", created="2026-10-03", due="")
    task("wrong-month", created="2026-10-03", due="2026-11-01")
    task("foreign-private", user="99")
    task("foreign-assigned", user="99")
    task("revoked", user="99", team="revoked")
    task("clinic-workspace", workspace="clinic")
    task("malformed", created="2026-10-01", due="2026-10-30bad")
    conn.execute("UPDATE tasks SET assignee_id='42' WHERE id='foreign-assigned'")
    conn.executemany("INSERT INTO team_members VALUES (?,?,?)", [
        ("shared", "42", "viewer"), ("shared", "99", "owner"),
        ("revoked", "99", "owner"),
    ])

    def sql_all(table, where="", params=()):
        sql = "SELECT * FROM " + table + (" WHERE " + where if where else "")  # nosec B608 - trusted application predicate
        return [dict(row) for row in conn.execute(sql, params)]

    monkeypatch.setattr(reports, "sync_all", sql_all)
    monkeypatch.setattr(dashboard, "sync_query_one", lambda sql, params=(): dict(conn.execute(sql, params).fetchone()))
    monkeypatch.setattr(dashboard, "_access", lambda token: {"user_id": "42", "bot_key": "default"})
    yield conn
    conn.close()


def test_calendar_shows_all_deadlines_even_if_created_before_period(core_db):
    result = dashboard.dashboard_report(
        "token", section="calendar", page=7, page_size=25,
        period="custom", start_value="2026-10-01", end_value="2026-10-31",
    )
    assert result["section"] == "calendar"
    assert result["pages"] == 1 and result["page"] == 1
    assert result["pagination_mode"] == "none"
    assert result["total"] == 42  # 40 old, one new, one shared-team
    assert len(result["rows"]) == 42
    assert sum(day["count"] for day in result["days"]) == 42
    assert len(result["days"]) == 31
    assert result["days"][9]["count"] == 41
    assert result["days"][10]["count"] == 1
    assert result["days"][9]["jalali_date"] == "1405/07/18"
    assert result["days"][9]["weekday"] == 0  # Saturday-first layout


def test_calendar_scope_membership_revoke_and_structured_filters(core_db):
    params = {
        "section": "calendar", "period": "custom",
        "start_value": "2026-10-01", "end_value": "2026-10-31",
    }
    report = dashboard.dashboard_report("token", search='{"status":"in_progress"}', **params)
    assert {item["id"] for item in report["rows"]} == {"today-created"}
    assert report["total"] == 1
    original = dashboard.dashboard_report("token", **params)
    assert "authorized-team" in {item["id"] for item in original["rows"]}
    assert "foreign-private" not in str(original["rows"])
    assert "foreign-assigned" not in str(original["rows"])
    assert "clinic-workspace" not in str(original["rows"])
    assert "revoked" not in str(original["rows"])
    core_db.execute("DELETE FROM team_members WHERE team_id='shared' AND user_id='42'")
    after = dashboard.dashboard_report("token", **params)
    assert after["total"] == original["total"] - 1
    assert "authorized-team" not in {item["id"] for item in after["rows"]}


def test_calendar_preserves_filter_search_and_includes_due_on_month_boundaries(core_db):
    core_db.execute(
        "UPDATE tasks SET deadline='2026-10-01' WHERE id='old-00'"
    )
    core_db.execute(
        "UPDATE tasks SET deadline='2026-10-31' WHERE id='old-01'"
    )
    report = dashboard.dashboard_report(
        "token", section="calendar", period="custom",
        start_value="2026-10-01", end_value="2026-10-31",
        search='{"q":"old-00","priority":"medium"}',
    )
    assert [r["id"] for r in report["rows"]] == ["old-00"]
    assert report["days"][0]["count"] == 1
    assert report["days"][-1]["count"] == 0
    result = dashboard.dashboard_report(
        "token", section="calendar", period="custom",
        start_value="2026-10-31", end_value="2026-10-01",
    )
    assert result["range"] == {"start": "2026-10-01", "end": "2026-10-31"}
    assert result["days"][-1]["count"] == 1


@pytest.mark.parametrize("anchor", [
    date(2025, 3, 19), date(2025, 3, 20), date(2026, 3, 20),
    date(2026, 3, 21), date(2026, 12, 31), date(2027, 1, 1),
])
def test_heatmap_jalali_month_navigation_is_contiguous_and_uses_true_solar_bounds(anchor):
    nav = dashboard._jalali_month_navigation(anchor)
    jy, jm, _ = dashboard.gregorian_to_jalali(anchor.year, anchor.month, anchor.day)
    current = nav["current"]
    prev = nav["previous"]
    next_ = nav["next"]
    assert nav["calendar"] == "jalali"
    assert (nav["anchor_year"], nav["anchor_month"]) == (jy, jm)
    assert date.fromisoformat(current["start"]) <= anchor <= date.fromisoformat(current["end"])
    assert date.fromisoformat(prev["end"]) + timedelta(days=1) == date.fromisoformat(current["start"])
    assert date.fromisoformat(current["end"]) + timedelta(days=1) == date.fromisoformat(next_["start"])
    assert date.fromisoformat(current["start"]) == jdatetime.date(jy, jm, 1).togregorian()
    assert (date.fromisoformat(next_["start"]) - date.fromisoformat(current["start"])).days in {29, 30, 31}


def test_esfand_leap_year_and_new_year_navigation():
    # In the leap Jalali year 1403, Esfand includes day 30.
    start = jdatetime.date(1403, 12, 1).togregorian()
    nav = dashboard._jalali_month_navigation(start)
    assert nav["current"]["end"] == jdatetime.date(1403, 12, 30).togregorian().isoformat()
    assert nav["next"]["start"] == jdatetime.date(1404, 1, 1).togregorian().isoformat()


def test_heatmap_and_calendar_navigation_obey_global_date_envelope(core_db):
    lower = dashboard._jalali_month_navigation(date(1900, 1, 1))
    upper = dashboard._jalali_month_navigation(date(2100, 12, 31))
    assert lower["previous"] is None
    assert upper["next"] is None
    data = dashboard.dashboard_report(
        "token", section="heatmap", period="custom",
        start_value="2026-10-01", end_value="2026-10-31",
    )
    assert data["navigation"]["calendar"] == "jalali"
    assert data["navigation"]["current"]["start"] != "2026-10-01"
    report = dashboard.dashboard_report(
        "token", section="calendar", period="custom",
        start_value="2026-10-01", end_value="2026-10-31",
    )
    assert report["navigation"]["jalali"]["previous"]
    assert report["navigation"]["gregorian"]["previous"]["start"] == "2026-09-01"


def test_report_calendar_ui_has_RTL_seven_day_grid_day_inspection_and_filter_safe_navigation():
    ui = (Path(__file__).resolve().parents[1] / "webapp" / "report_dashboard.js").read_text(encoding="utf-8")
    assert "calendar-grid{display:grid;grid-template-columns:repeat(7" in ui
    assert "direction:rtl" in ui
    assert "data-calendar-day=" in ui
    assert "aria-pressed=" in ui
    assert "selectedTasks = tasksByDay.get(selected) || []" in ui
    assert "data-calendar-mode=" in ui
    assert "data-calendar-shift=" in ui
    assert "new URLSearchParams(params())" in ui
    assert "nav.previous" in ui and "nav.next" in ui
    heatmap_fragment = ui[ui.index("if (section === 'heatmap')"):ui.index("if (section === 'calendar')")]
    assert "Date.UTC(firstDate" not in heatmap_fragment
    assert "window.__heatmapShift = shiftMonth;" in heatmap_fragment
