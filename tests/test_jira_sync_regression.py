import logging

from services import jira_service


def _task(**overrides):
    task = {
        "id": "task-1",
        "user_id": "42",
        "title": "Old title",
        "description": "",
        "status": "pending",
        "priority": "medium",
        "deadline": "",
        "category": "",
        "tags": "",
        "created_at": "2026-01-01 00:00",
        "completed_at": "",
        "team_id": "",
        "assignee_id": "",
        "assignee_name": "",
        "assignee_username": "",
        "jira_key": "PROJ-1",
        "jira_sync_hash": "",
    }
    task.update(overrides)
    return task


def _issue(summary="Updated from Jira"):
    return {
        "key": "PROJ-1",
        "fields": {
            "summary": summary,
            "description": "Inbound description",
            "status": {"name": "In Progress"},
            "duedate": "2026-10-10",
            "priority": {"name": "High"},
        },
    }


def test_inbound_jira_change_persists_with_explicit_bot_key(monkeypatch):
    task = _task()
    connection = {"user_id": "42", "bot_key": "bot_a", "project_key": "PROJ"}
    writes = []
    links = []

    monkeypatch.setattr(jira_service, "read_tasks", lambda: [task])
    monkeypatch.setattr(jira_service, "_attach_links", lambda tasks, bot_key: None)
    monkeypatch.setattr(
        jira_service,
        "_jira_issues_for_user",
        lambda c, bot_key: [_issue()] if bot_key == "bot_a" else [],
    )
    monkeypatch.setattr(jira_service, "_linked_task", lambda tasks, key, bot_key: None)
    monkeypatch.setattr(
        jira_service,
        "_write_all",
        lambda tasks, bot_key: writes.append((bot_key, tasks[0]["title"])),
    )
    monkeypatch.setattr(
        jira_service,
        "_persist_link",
        lambda task, key, sync_hash, bot_key: links.append((bot_key, key)),
    )
    monkeypatch.setattr(jira_service, "get_current_bot_key", lambda: "bot_b")

    result = jira_service.sync_connection(connection, "bot_a")

    assert result["success"] is True
    assert result["updated"] == 1
    assert writes == [("bot_a", "Updated from Jira")]
    assert links == [("bot_a", "PROJ-1")]
    assert task["status"] == "in_progress"


def test_write_all_uses_supplied_bot_key_not_ambient_context(monkeypatch):
    calls = []
    monkeypatch.setattr(jira_service, "sync_all", lambda *args: [])
    monkeypatch.setattr(
        jira_service,
        "sync_execute",
        lambda sql, params=(): calls.append((sql, params)),
    )
    monkeypatch.setattr(jira_service, "get_current_bot_key", lambda: "bot_b")

    jira_service._write_all([_task(jira_key="")], "bot_a")

    assert len(calls) == 1
    assert calls[0][1][1] == "bot_a"


def test_inbound_persistence_failure_is_reported_and_logged(monkeypatch, caplog):
    task = _task()
    connection = {"user_id": "42", "bot_key": "bot_a", "project_key": "PROJ"}

    monkeypatch.setattr(jira_service, "read_tasks", lambda: [task])
    monkeypatch.setattr(jira_service, "_attach_links", lambda tasks, bot_key: None)
    monkeypatch.setattr(jira_service, "_jira_issues_for_user", lambda c, bot_key: [_issue()])
    monkeypatch.setattr(jira_service, "_linked_task", lambda tasks, key, bot_key: None)
    monkeypatch.setattr(
        jira_service,
        "_write_all",
        lambda tasks, bot_key: (_ for _ in ()).throw(RuntimeError("db write failed")),
    )

    with caplog.at_level(logging.ERROR, logger="services.jira_service"):
        result = jira_service.sync_connection(connection, "bot_a")

    assert result["success"] is False
    assert result["partial"] is False
    assert result["updated"] == 0
    assert result["errors"][0]["operation"] == "persist_inbound"
    assert "provider=jira" in caplog.text
    assert "bot_key=bot_a" in caplog.text
    assert "operation=persist_inbound" in caplog.text


def test_all_connections_reports_partial_failure(monkeypatch):
    connections = [
        {"user_id": "1", "bot_key": "bot_a", "project_key": "GOOD"},
        {"user_id": "2", "bot_key": "bot_a", "project_key": "BAD"},
    ]
    updates = []

    monkeypatch.setattr(jira_service, "_load_connections", lambda: connections)

    def sync_connection(connection, bot_key):
        if connection["user_id"] == "2":
            raise RuntimeError("jira unavailable")
        return {
            "success": True,
            "partial": False,
            "updated": 2,
            "failed": 0,
            "errors": [],
        }

    monkeypatch.setattr(jira_service, "sync_connection", sync_connection)
    monkeypatch.setattr(
        jira_service,
        "sync_execute",
        lambda sql, params=(): updates.append((sql, params)),
    )

    result = jira_service.sync_all_connections("bot_a")

    assert result["success"] is False
    assert result["partial"] is True
    assert result["updated"] == 2
    assert result["connections"] == 2
    assert result["failed_connections"] == 1
    assert len(result["results"]) == 2
    assert len(updates) == 1
    assert updates[0][1][1] == "bot_a"
    assert updates[0][1][2] == "1"
