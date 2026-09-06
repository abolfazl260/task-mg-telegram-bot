"""End-to-end user journey for the core task lifecycle.

The journey uses the real task service and an isolated test database. It does
not call Telegram or external services, so it is deterministic and safe to run
in CI without leaving test data behind.
"""

import time

import pytest

from services import task_service


@pytest.mark.asyncio
async def test_user_can_create_view_edit_comment_and_complete_task(test_db, monkeypatch):
    user_id = "e2e-user-1001"
    title = "E2E Test Task"
    started_at = time.perf_counter()

    print("\n[E2E TEST] starting real user task journey")
    print("[E2E TEST] database=isolated test database")

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
    print(f"[E2E TEST] 1/7 CREATE TASK      -> id={task_id}")

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
    print("[E2E TEST] 2/7 READ TASK        -> all created fields verified")

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
    print("[E2E TEST] 3/7 UPDATE TASK      -> updated fields persisted")

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
    print("[E2E TEST] 4/7 ADD COMMENT      -> comment persisted and reloaded")

    # 5. User completes the task.
    completed = await task_service.update_task_status_async(task_id, "done")
    assert completed is True
    print("[E2E TEST] 5/7 COMPLETE TASK    -> status changed to done")

    # 6. Final read verifies the complete persisted state.
    task = await task_service.get_task_by_id_async(task_id)
    assert task["status"] == "done"
    assert task["completed_at"]
    assert task["title"] == "E2E Test Task - Updated"
    assert task["priority"] == "medium"
    assert task["category"] == "Work"
    assert task["tags"] == "e2e,test,updated"
    assert task["description"] == "Updated by the end-to-end journey."
    print("[E2E TEST] 6/7 FINAL READ       -> complete task state verified")

    # 7. User still sees the task and its comment in the persisted data.
    tasks = await task_service.get_all_user_tasks_async(user_id)
    matching = [item for item in tasks if item["id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "done"
    assert await task_service.get_task_comments_async(task_id) == comments

    elapsed = time.perf_counter() - started_at
    print("[E2E TEST] 7/7 DATABASE CHECK   -> task and comment still linked")
    print(f"[E2E TEST] elapsed={elapsed:.2f}s")
    print("[E2E TEST] RESULT=PASSED")
