import pytest

from services import task_service


@pytest.mark.asyncio
async def test_task_crud_status_assignment_and_delete(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")

    task_id = await task_service.create_task_async(
        100, "Write tests", "high", "2026-08-20", "dev", "pytest", "details"
    )
    task = await task_service.get_task_by_id_async(task_id)
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"

    assert await task_service.update_task_status_async(task_id, "in_progress")
    assert (await task_service.get_task_by_id_async(task_id))["status"] == "in_progress"

    assert await task_service.assign_task_async(
        task_id, {"user_id": 200, "display_name": "Alice", "username": "alice"}, 100
    )
    task = await task_service.get_task_by_id_async(task_id)
    assert task["assignee_id"] == "200"
    assert task["assignee_name"] == "Alice"

    history = await task_service.get_assignment_history_async(task_id)
    assert history[-1]["new_assignee_name"] == "Alice"

    assert await task_service.update_task_status_async(task_id, "done")
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
    assert not await task_service.update_task_status_async(task_id, "unknown")
