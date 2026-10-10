"""Issue #222: shared Core report population, authorization and export regressions."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from webapp import activity_feed, report_dashboard_service, reports


def _fixture():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE tasks (
          id TEXT PRIMARY KEY, user_id TEXT, bot_key TEXT, workspace_id TEXT,
          team_id TEXT, assignee_id TEXT, title TEXT, created_at TEXT,
          completed_at TEXT, deadline TEXT, category TEXT, tags TEXT,
          status TEXT, priority TEXT, assignee_name TEXT, assignee_username TEXT
        );
        CREATE TABLE team_members(team_id TEXT, user_id TEXT, role TEXT);
        CREATE TABLE task_comments (
          id INTEGER, task_id TEXT, created_at TEXT, content_json TEXT,
          author_name TEXT, author_username TEXT
        );
        CREATE TABLE task_assignment_history (
          id INTEGER, task_id TEXT, created_at TEXT, action TEXT,
          old_assignee_name TEXT, new_assignee_name TEXT, actor_id TEXT
        );
    """)
    records = [
        # id, creator, provenance, workspace, team, assignee
        ("personal", "42", "alpha", None, None, None),
        ("cross-profile", "42", "beta", None, None, None),
        ("team-editor", "99", "beta", None, "editor-team", "99"),
        ("team-viewer", "98", "alpha", None, "viewer-team", "42"),
        ("assignee-only", "99", "alpha", None, None, "42"),
        ("foreign", "99", "alpha", None, None, None),
        ("clinic", "42", "alpha", "clinic-workspace", None, "42"),
        ("revoked", "99", "beta", None, "revoked-team", None),
        ("former-owner", "42", "beta", None, "revoked-team", "42"),
        ("previous", "42", "alpha", None, None, None),
    ]
    for task_id, owner, bot, workspace, team, assignee in records:
        month = "09" if task_id == "previous" else "10"
        conn.execute(
            """INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, owner, bot, workspace, team, assignee, task_id,
             f"2026-{month}-05T10:00:00Z", "", "", "work", "",
             "pending", "medium", "", ""),
        )
    conn.executemany(
        "INSERT INTO team_members(team_id,user_id,role) VALUES (?,?,?)",
        [
            ("editor-team", "42", "editor"), ("viewer-team", "42", "viewer"),
            ("editor-team", "99", "owner"),
            ("viewer-team", "98", "owner"),
            ("revoked-team", "99", "owner"),
        ],
    )
    conn.executemany("INSERT INTO task_comments VALUES (?,?,?,?,?,?)", [
        (1, "team-editor", "2026-10-07T10:00:00Z", '{"type":"text","text":"Team note"}', "Owner", ""),
        (2, "foreign", "2026-10-07T10:00:00Z", '{"type":"text","text":"Forbidden note"}', "Owner", ""),
    ])
    conn.commit()
    return conn


@pytest.fixture
def report_db(monkeypatch):
    conn = _fixture()
    def query(sql, params=()):
        return [dict(row) for row in conn.execute(sql, params)]

    def sync_all(table, where="", params=()):
        return query("SELECT * FROM " + table + (" WHERE " + where if where else ""), params)  # nosec B608 - app's fixed table and parameterized scope

    monkeypatch.setattr(reports, "sync_all", sync_all)
    monkeypatch.setattr(activity_feed, "sync_all", sync_all)
    monkeypatch.setattr(report_dashboard_service, "sync_query_one", lambda sql, params=(): query(sql, params)[0])
    token_access = {"user_id": "42", "bot_key": "alpha", "report_type": "monthly"}
    monkeypatch.setattr(reports, "resolve_report_token", lambda token: token_access)
    monkeypatch.setattr(report_dashboard_service, "_access", lambda token: token_access)
    yield conn
    conn.close()


def _visible_ids(access):
    return {row["id"] for row in reports._task_rows(access, "created_at>=? AND created_at<?", ("2026-10-01", "2026-11-01"))}


def test_report_matches_core_private_and_team_membership_scopes(report_db):
    alpha = {"user_id": "42", "bot_key": "alpha"}
    beta = {"user_id": "42", "bot_key": "beta"}
    allowed = {"personal", "cross-profile", "team-editor", "team-viewer"}
    assert _visible_ids(alpha) == allowed
    assert _visible_ids(beta) == allowed, "Core tasks are shared; bot_key is provenance"
    report_db.execute("DELETE FROM team_members WHERE user_id='42' AND team_id='editor-team'")
    assert _visible_ids(alpha) == allowed - {"team-editor"}
    report_db.execute("DELETE FROM team_members WHERE user_id='42' AND team_id='viewer-team'")
    assert _visible_ids(alpha) == {"personal", "cross-profile"}
    assert _visible_ids({"user_id": "100", "bot_key": "alpha"}) == set()


def test_dashboard_counts_rows_and_full_export_use_same_authorized_population(report_db):
    access = {"user_id": "42", "bot_key": "alpha"}
    kwargs = {"period": "custom", "start_value": "2026-10-01", "end_value": "2026-10-31"}
    summary = report_dashboard_service.dashboard_report("token", **kwargs)
    table = report_dashboard_service.dashboard_report("token", section="tasks", page_size=2, **kwargs)
    all_rows = report_dashboard_service.dashboard_report("token", section="tasks", page_size=0, **kwargs)
    assert summary["summary"]["total"] == 4
    assert summary["summary"]["total_change"]["previous_total"] == 1
    assert table["total"] == summary["summary"]["total"]
    assert len(table["rows"]) == 2 and table["pages"] == 2
    assert {item["id"] for item in all_rows["rows"]} == _visible_ids(access)
    assert all_rows["total"] == len(all_rows["rows"]) == 4
    report_db.execute("DELETE FROM team_members WHERE user_id='42' AND team_id='editor-team'")
    after = report_dashboard_service.dashboard_report("token", section="tasks", page_size=0, **kwargs)
    assert "team-editor" not in {item["id"] for item in after["rows"]}
    assert after["total"] == 3


def test_legacy_sections_and_activity_exclude_revoked_and_unrelated_data(report_db):
    legacy = reports.monthly_report("token", section="tasks")
    assert {x["id"] for x in legacy["rows"]} == {"personal", "cross-profile", "team-editor", "team-viewer"}
    feed = activity_feed.activity_feed(
        {"user_id": "42", "bot_key": "alpha"},
        start=date(2026, 10, 1), end=date(2026, 10, 31),
    )
    visible_events = {e["task_id"] for e in feed["events"]}
    assert visible_events == {"personal", "cross-profile", "team-editor", "team-viewer"}
    assert any(e["id"] == "comment-1" for e in feed["events"])
    assert not any(e["id"] == "comment-2" for e in feed["events"])
    assert "Forbidden note" not in str(feed)
    report_db.execute("DELETE FROM team_members WHERE team_id='editor-team' AND user_id='42'")
    feed_after = activity_feed.activity_feed(
        {"user_id": "42", "bot_key": "alpha"},
        start=date(2026, 10, 1), end=date(2026, 10, 31),
    )
    assert not any(e["task_id"] == "team-editor" for e in feed_after["events"])
