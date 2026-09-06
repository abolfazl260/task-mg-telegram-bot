"""End-to-end user journey for the core task lifecycle.

The journey uses the real task service and an isolated test database. It does
not call Telegram or external services, so it is deterministic and safe to run
in CI without leaving test data behind.
"""

import pytest

from services import task_service


@pytest.mark.asyncio
async def test_user_can_create_view_edit_comment_and_complete_task(test_db, monkeypatch):
    user_id = "e2e-user-1001"
    title = "E2E Test Task"

    # Keep bot provenance deterministic without touching application settings.
    monkeypatch.setattr(task_service, "_bot", lambda: "e2e-test-bot")

    # 1. User creates a task.
    task_id = await task_service.create_task_async(
        user_id=user_id,
        title=title,
        priority="high",
        deadline="2026-09-30",
        category="Work",
        tags="e2e,test",
        description="Created by the end-to-end user journey.",
    )
    assert task_id

    # 2. User opens the task and sees exactly what was submitted.
    task = await task_service.get_task_by_id_async(task_id)
    assert task is not None
    assert task["user_id"] == user_id
    assert task["title"] == title
    assert task["priority"] == "high"
    assert task["status"] == "pending"
    assert task["deadline"] == "2026-09-30"
    assert task["category"] == "Work"
    assert task["tags"] == "e2e,test"
    assert task["description"] == "Created by the end-to-end user journey."

    # 3. User edits the task.
    updated = await task_service.update_task_async(
        task_id,
        user_id,
        title="E2E Test Task - Updated",
        priority="medium",
        description="Updated by the end-to-end journey.",
        tags="e2e,test,updated",
    )
    assert updated is True

    task = await task_service.get_task_by_id_async(task_id)
    assert task["title"] == "E2E Test Task - Updated"
    assert task["priority"] == "medium"
    assert task["description"] == "Updated by the end-to-end journey."
    assert task["tags"] == "e2e,test,updated"
    assert task["category"] == "Work"
    assert task["deadline"] == "2026-09-30"

    # 4. User adds a comment and then verifies it was persisted.
    comment = {
        "text": "E2E comment persisted successfully",
        "type": "text",
    }
    added = await task_service.add_task_comment_async(
        task_id,
        {"id": user_id, "full_name": "E2E User", "username": "e2e_user"},
        comment,
    )
    assert added is True

    comments = await task_service.get_task_comments_async(task_id)
    assert len(comments) == 1
    assert comments[0]["author_id"] == user_id
    assert comments[0]["author_name"] == "E2E User"
    assert comments[0]["author_username"] == "e2e_user"
    assert comments[0]["text"] == "E2E comment persisted successfully"
    assert comments[0]["type"] == "text"

    # 5. User completes the task.
    completed = await task_service.update_task_status_async(task_id, "done")
    assert completed is True

    # 6. Final read verifies the complete persisted state.
    task = await task_service.get_task_by_id_async(task_id)
    assert task["status"] == "done"
    assert task["completed_at"]
    assert task["title"] == "E2E Test Task - Updated"
    assert task["priority"] == "medium"
    assert task["category"] == "Work"
    assert task["tags"] == "e2e,test,updated"
    assert task["description"] == "Updated by the end-to-end journey."

    # 7. The task is still visible in the user's complete task list and the
    # comment remains attached to the same task.
    tasks = await task_service.get_all_user_tasks_async(user_id)
    matching = [item for item in tasks if item["id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "done"
    assert await task_service.get_task_comments_async(task_id) == comments
