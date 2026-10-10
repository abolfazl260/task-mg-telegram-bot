"""Integration tests for date-bounded activity queries on SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from webapp import activity_feed as feed_module


def _fixture_connection():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE tasks (
          id TEXT PRIMARY KEY, bot_key TEXT, user_id TEXT, workspace_id TEXT,
          title TEXT, status TEXT, created_at TEXT, completed_at TEXT,
          assignee_name TEXT, creator_name TEXT
        );
        CREATE TABLE task_comments (
          id INTEGER PRIMARY KEY, task_id TEXT, author_name TEXT,
          content_json TEXT, created_at TEXT
        );
        CREATE TABLE task_assignment_history (
          id INTEGER PRIMARY KEY, task_id TEXT, action TEXT, created_at TEXT,
          actor_name TEXT, old_assignee_name TEXT, new_assignee_name TEXT
        );
        """
    )
    tasks = [
        ("old-done", "bot", "42", None, "Old but finished now", "done",
         "2026-06-01T09:00:00Z", "2026-10-03T09:00:00Z", "Someone", "Owner"),
        ("old-active", "bot", "42", None, "Old but changed now", "pending",
         "2026-06-02T09:00:00Z", "", "Someone", "Owner"),
        ("new", "bot", "42", None, "New task", "pending",
         "2026-10-06T09:00:00Z", "", "", "Owner"),
        ("other-bot", "other", "42", None, "Forbidden bot task", "pending",
         "2026-10-06T09:00:00Z", "", "", "Owner"),
        ("other-user", "bot", "99", None, "Forbidden other user", "pending",
         "2026-10-06T09:00:00Z", "", "", "Owner"),
        ("workspace", "bot", "42", "clinic", "Forbidden workspace", "pending",
         "2026-10-06T09:00:00Z", "", "", "Owner"),
    ]
    db.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)", tasks)
    comments = [
        (1, "old-active", "Editor", json.dumps({"type": "text", "text": "Working"}), "2026-10-04T10:00:00Z"),
        (2, "other-bot", "Editor", json.dumps({"type": "text", "text": "Hidden"}), "2026-10-04T10:00:00Z"),
        (3, "old-active", "Editor", json.dumps({"type": "text", "text": "Old event"}), "2026-06-03T10:00:00Z"),
    ]
    db.executemany("INSERT INTO task_comments VALUES (?,?,?,?,?)", comments)
    assignments = [
        (1, "old-active", "assigned", "2026-10-05T11:00:00Z", "Owner", "", "Someone"),
        (2, "other-user", "assigned", "2026-10-05T11:00:00Z", "Owner", "", "Someone"),
    ]
    db.executemany(
        "INSERT INTO task_assignment_history VALUES (?,?,?,?,?,?,?)", assignments
    )
    return db


def test_activity_feed_limits_sql_scans_and_keeps_prior_task_metadata(monkeypatch):
    db = _fixture_connection()
    reads = []

    def sql_sync_all(table, where, params):
        reads.append((table, where, params))
        return [
            dict(row)
            for row in db.execute(f"SELECT * FROM {table} WHERE {where}", params)  # nosec B608 - test uses app-generated where and known tables
        ]

    monkeypatch.setattr(feed_module, "sync_all", sql_sync_all)
    access = {"bot_key": "bot", "user_id": "42"}
    output = feed_module.activity_feed(
        access, start=date(2026, 10, 1), end=date(2026, 10, 10)
    )
    assert output["total"] == 4
    ids = {event["id"] for event in output["events"]}
    assert ids == {
        "task-completed-old-done",
        "task-created-new",
        "comment-1",
        "assignment-1",
    }
    assert all("Forbidden" not in event["task_title"] for event in output["events"])
    old_event = next(event for event in output["events"] if event["id"] == "comment-1")
    assert old_event["task_title"] == "Old but changed now"
    assert len(reads) == 4, "Three bounded event scans and one scoped task metadata lookup"
    for table, where, _ in reads:
        if table in {"task_comments", "task_assignment_history"}:
            assert "created_at>=?" in where
            assert "created_at<?" in where
        if table == "tasks" and "id IN" not in where:
            assert "created_at>=?" in where
            assert "completed_at>=?" in where
    db.close()


def test_activity_feed_preserves_unbounded_and_search_contract(monkeypatch):
    db = _fixture_connection()

    def sql_sync_all(table, where, params):
        return [
            dict(row)
            for row in db.execute(f"SELECT * FROM {table} WHERE {where}", params)  # nosec B608 - test uses app-generated where and known tables
        ]

    monkeypatch.setattr(feed_module, "sync_all", sql_sync_all)
    access = {"bot_key": "bot", "user_id": "42"}
    all_events = feed_module.activity_feed(access)
    assert all_events["total"] == 7
    matched = feed_module.activity_feed(access, query="Working")
    assert matched["total"] == 1
    assert matched["events"][0]["id"] == "comment-1"
    limited = feed_module.activity_feed(access, limit=2)
    assert limited["total"] == all_events["total"]
    assert len(limited["events"]) == 2
    db.close()
