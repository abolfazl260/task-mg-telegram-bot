from __future__ import annotations

import pytest

from services import task_service


@pytest.mark.asyncio
async def test_create_list_and_summarize_children(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    patient = await task_service.create_task_async(
        1, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    first = await task_service.create_child_task_async(
        patient, 1, "Visit 1", work_item_type="session"
    )
    second = await task_service.create_child_task_async(
        patient, 1, "Visit 2", work_item_type="session"
    )

    children = await task_service.list_child_tasks_async(patient, 1, limit=1)
    assert [item["id"] for item in children] == [first]
    assert (await task_service.get_parent_task_async(first))["id"] == patient
    assert (await task_service.count_child_tasks_async(patient, 1))["total"] == 2
    assert second != first


@pytest.mark.asyncio
async def test_hierarchy_rejects_invalid_type_and_cycles(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    patient = await task_service.create_task_async(
        2, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    session = await task_service.create_child_task_async(
        patient, 2, "Visit", work_item_type="session"
    )
    with pytest.raises(ValueError, match="invalid_child_type|invalid_parent_type"):
        await task_service.create_child_task_async(
            session, 2, "Nested visit", work_item_type="session"
        )
    with pytest.raises(ValueError, match="hierarchy_cycle"):
        await task_service.move_child_task_async(patient, session, 2)


@pytest.mark.asyncio
async def test_hierarchy_authorization_and_scope_are_enforced(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    parent = await task_service.create_task_async(
        3, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    with pytest.raises(PermissionError, match="permission_denied"):
        await task_service.create_child_task_async(
            parent, 4, "Visit", work_item_type="session"
        )


@pytest.mark.asyncio
async def test_archive_parent_preserves_children(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    parent = await task_service.create_task_async(
        5, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    child = await task_service.create_child_task_async(
        parent, 5, "Visit", work_item_type="session"
    )
    assert await task_service.archive_task_async(parent, 5)
    assert (await task_service.get_task_by_id_async(child))["parent_task_id"] == parent
    assert (await task_service.count_child_tasks_async(parent, 5))["archived"] == 0
