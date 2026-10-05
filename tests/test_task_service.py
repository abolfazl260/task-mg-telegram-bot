import pytest

from services import task_service, team_service


@pytest.mark.asyncio
async def test_task_crud_status_assignment_and_delete(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")

    task_id = await task_service.create_task_async(
        100, "Write tests", "high", "2026-08-20", "dev", "pytest", "details"
    )
    task = await task_service.get_task_by_id_async(task_id)
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"

    assert await task_service.update_task_status_async(task_id, "in_progress", 100)
    assert (await task_service.get_task_by_id_async(task_id))["status"] == "in_progress"

    assert await task_service.assign_task_async(
        task_id, {"user_id": 200, "display_name": "Alice", "username": "alice"}, 100
    )
    task = await task_service.get_task_by_id_async(task_id)
    assert task["assignee_id"] == "200"
    assert task["assignee_name"] == "Alice"

    history = await task_service.get_assignment_history_async(task_id)
    assert history[-1]["new_assignee_name"] == "Alice"

    assert await task_service.update_task_status_async(task_id, "done", 100)
    assert (await task_service.get_task_by_id_async(task_id))["completed_at"]

    # Deletion is exercised directly against the same isolated DB.
    from services.database import execute
    await execute("DELETE FROM tasks WHERE id=?", (task_id,))
    assert await task_service.get_task_by_id_async(task_id) is None


@pytest.mark.asyncio
async def test_task_tag_search(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")
    await task_service.create_task_async(100, "Deploy app", "medium", "", "dev", "release,urgent")
    await task_service.create_task_async(100, "Buy milk", "low", "", "home", "shopping")

    results = await task_service.search_tasks_async(100, "urgent")
    assert [r["title"] for r in results] == ["Deploy app"]


@pytest.mark.asyncio
async def test_invalid_status_is_rejected(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")
    task_id = await task_service.create_task_async(100, "Task", "medium", "", "", "")
    assert not await task_service.update_task_status_async(task_id, "unknown", 100)


@pytest.mark.asyncio
async def test_visibility_filters_in_database_without_full_table_read(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")

    personal_id = await task_service.create_task_async(
        100, "Personal visible", "medium", "", "personal", ""
    )
    await task_service.create_task_async(
        300, "Unrelated personal", "medium", "", "personal", ""
    )

    shared_team = await team_service.acreate_team(200, "Shared team")
    joined, _, _ = await team_service.ajoin_team_by_code(
        100, shared_team["viewer_code"]
    )
    assert joined
    shared_id = await task_service.create_task_async(
        200,
        "Shared visible",
        "medium",
        "",
        "team",
        "",
        team_id=shared_team["team_id"],
    )

    other_team = await team_service.acreate_team(400, "Other team")
    await task_service.create_task_async(
        400,
        "Unrelated team",
        "medium",
        "",
        "team",
        "",
        team_id=other_team["team_id"],
    )

    await task_service.update_task_status_async(shared_id, "done", 200)

    async def fail_full_table_read():
        raise AssertionError("visibility must not read the entire tasks table")

    monkeypatch.setattr(task_service, "read_tasks_async", fail_full_table_read)

    visible = await task_service.get_all_user_tasks_async(100)
    assert {task["id"] for task in visible} == {personal_id, shared_id}

    active = await task_service.get_active_tasks_async(100)
    assert {task["id"] for task in active} == {personal_id}
