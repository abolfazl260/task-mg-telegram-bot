"""Independent Core report cohorts and completion KPI regression tests (#225)."""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from webapp import report_dashboard_service as dashboard
from webapp import report_export, reports


@pytest.fixture
def report_database(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE tasks (
          id TEXT PRIMARY KEY, user_id TEXT, bot_key TEXT, team_id TEXT,
          workspace_id TEXT, title TEXT, status TEXT, priority TEXT,
          created_at TEXT, completed_at TEXT, deadline TEXT, category TEXT,
          assignee_id TEXT, assignee_name TEXT, assignee_username TEXT, tags TEXT
        );
        CREATE TABLE team_members(team_id TEXT, user_id TEXT, role TEXT);
        """
    )

    def task(identifier, *, owner="42", bot="bot-a", team=None, workspace=None,
             created="2026-08-01T12:00:00Z", completed="", due="", status="pending"):
        db.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (identifier, owner, bot, team, workspace, identifier, status,
             "medium", created, completed, due, "work", None, "", "", ""),
        )

    # Current (UTC 2026-10) open backlog must include historical creation.
    task("old-overdue", created="2026-02-01", due="2026-09-01")
    task("current-overdue", created="2026-09-05", due="2026-09-30")
    task("team-overdue", owner="99", team="member-team", created="2025-01-01",
         due="2026-08-10", bot="bot-b")
    task("due-today", created="2026-03-01", due="2026-10-10")
    task("due-future", created="2026-03-01", due="2026-11-10")
    task("cancelled-overdue", status="cancelled", due="2026-01-01")
    task("completed-late", status="done", created="2026-02-01",
         completed="2026-09-10T15:00:00Z", due="2026-09-08")
    task("completed-on-time", status="done", created="2026-01-01",
         completed="2026-09-19T15:00:00Z", due="2026-09-20")
    task("completed-utc-offset", status="done", created="2026-02-01",
         completed="2026-10-01T00:15:00+02:00", due="2026-09-30")
    task("completed-outside-utc", status="done", created="2026-02-01",
         completed="2026-09-30T23:15:00-02:00", due="2026-10-01")
    task("missing-completion", status="done", created="2026-09-06",
         completed="", due="2026-09-07")
    task("no-deadline", status="done", created="2026-09-07",
         completed="2026-09-08T12:00:00Z", due="")
    task("foreign-overdue", owner="99", due="2026-02-01")
    task("assignee-only-overdue", owner="99", due="2026-02-02")
    task("revoked-overdue", owner="99", team="revoked", due="2026-02-03")
    task("clinic-overdue", workspace="clinic", due="2026-02-04")
    task("future-created", created="2030-01-01", due="2026-01-01")
    db.execute("UPDATE tasks SET assignee_id='42' WHERE id='assignee-only-overdue'")
    db.execute("INSERT INTO team_members VALUES ('member-team','42','viewer')")
    db.execute("INSERT INTO team_members VALUES ('revoked','99','owner')")
    db.commit()

    def sql_all(table, where="", params=()):
        return [dict(x) for x in db.execute(
            "SELECT * FROM " + table + (" WHERE " + where if where else ""), params  # nosec B608 - test uses trusted application-generated predicates
        )]

    monkeypatch.setattr(reports, "sync_all", sql_all)
    monkeypatch.setattr(dashboard, "sync_query_one", lambda sql, params=(): dict(db.execute(sql, params).fetchone()))
    monkeypatch.setattr(dashboard, "_access", lambda token: {"user_id": "42", "bot_key": "bot-a"})
    yield db
    db.close()


def _summary(**kwargs):
    return dashboard.dashboard_report(
        "signed-token", period="custom", start_value="2026-09-01",
        end_value="2026-09-30", **kwargs,
    )["summary"]


def test_backlog_includes_older_tasks_and_team_members_but_not_unauthorized(report_database, monkeypatch):
    # Stable server date independent of when tests are executed.
    original = dashboard.datetime

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 10, 12, tzinfo=tz or UTC)

    monkeypatch.setattr(dashboard, "datetime", FixedDatetime)
    summary = _summary()
    # Created-cohort remains the original meaning (no old overdue inflation).
    assert summary["total"] == 3
    assert summary["done"] == 2  # one with missing completed_at, one without deadline
    assert summary["overdue"] == 3
    assert summary["backlog_as_of_utc"] == "2026-10-10"
    assert summary["productivity"]["open_overdue"] == 3
    assert summary["productivity"]["open_on_track"] == 2
    assert summary["completed_in_period"] == 4
    assert summary["completed_with_deadline"] == 3
    assert summary["completed_on_time"] == 2
    assert summary["completed_late"] == 1
    assert summary["on_time_rate"] == 67
    assert summary["overdue_rate"] == 33
    report_database.execute(
        "DELETE FROM team_members WHERE team_id='member-team' AND user_id='42'"
    )
    after_revocation = _summary()
    assert after_revocation["overdue"] == 2
    assert after_revocation["completed_in_period"] == 3
    monkeypatch.setattr(dashboard, "datetime", original)


def test_period_completion_boundary_normalizes_offsets_and_absent_timestamps(report_database):
    completed = dashboard._query_completed_tasks(
        {"user_id": "42", "bot_key": "bot-a"},
        date(2026, 9, 1), date(2026, 9, 30),
    )
    ids = {row["id"] for row in completed}
    assert ids == {"completed-late", "completed-on-time", "completed-utc-offset", "no-deadline"}
    assert "completed-outside-utc" not in ids
    assert "missing-completion" not in ids
    assert dashboard._productivity_metrics([], completed_tasks=completed)["completed_with_deadline"] == 3


def test_empty_eligible_denominator_is_unavailable_not_perfect(report_database):
    # No completion with a deadline occurred in this interval.
    summary = dashboard.dashboard_report(
        "signed-token", period="custom", start_value="2026-07-01",
        end_value="2026-07-31",
    )["summary"]
    assert summary["completed_with_deadline"] == 0
    assert summary["on_time_rate"] is None
    assert summary["overdue_rate"] is None
    assert summary["productivity"]["on_time_rate"] is None
    assert dashboard._productivity_metrics([
        {"status": "done", "deadline": "2026-09-01", "completed_at": ""}
    ])["on_time_rate"] is None


def test_filters_have_separate_documented_populations(report_database, monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 10, 12, tzinfo=tz or UTC)

    monkeypatch.setattr(dashboard, "datetime", FixedDatetime)
    access = {"user_id": "42", "bot_key": "bot-a"}
    backlog = dashboard._open_deadline_counts(access, date(2026, 10, 10), filters={"status": "pending"})
    assert backlog == {"open_overdue": 3, "open_on_track": 2}
    filtered = dashboard.dashboard_report(
        "signed-token", period="custom", start_value="2026-09-01",
        end_value="2026-09-30", search='{"status":"done"}',
    )["summary"]
    assert filtered["overdue"] == 0
    assert filtered["productivity"]["open_on_track"] == 0
    assert filtered["completed_with_deadline"] == 3
    assert filtered["total"] == 2


def test_exported_kpis_match_api_and_display_null_as_dash(report_database, monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 10, 12, tzinfo=tz or UTC)

    monkeypatch.setattr(dashboard, "datetime", FixedDatetime)
    report = dashboard.dashboard_report(
        "signed-token", section="tasks", page_size=0, period="custom",
        start_value="2026-09-01", end_value="2026-09-30",
    )
    assert "old-overdue" not in {row["id"] for row in report["rows"]}
    assert report["summary"]["overdue"] == 3
    csv_bytes = report_export.ReportExportService.csv_bytes(report)
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert ["تکمیل‌شده در بازه انتخابی", "4"] in rows
    assert ["نرخ تکمیل به‌موقع در بازه", "67%"] in rows
    assert ["وظایف باز عقب‌افتاده تا 2026-10-10 UTC", "3"] in rows
    empty_report = dict(report, summary=dict(report["summary"], on_time_rate=None))
    assert ["نرخ تکمیل به‌موقع در بازه", "—"] in list(csv.reader(
        io.StringIO(report_export.ReportExportService.csv_bytes(empty_report).decode("utf-8-sig"))
    ))


def test_report_ui_labels_created_vs_completed_vs_live_backlog():
    source = (Path(__file__).parents[1] / "webapp" / "report_dashboard.js").read_text(encoding="utf-8")
    assert "'وظایف ایجادشده در بازه'" in source
    assert "'🎯 انجام به‌موقع در بازه'" in source
    assert "'Backlog باز عقب‌افتاده تا امروز UTC'" in source
    assert "prod.on_time_rate != null ? " in source
    assert ": '—';" in source
