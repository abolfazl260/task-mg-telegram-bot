from __future__ import annotations

import aiosqlite
import pytest

from services import database, task_service
from services.work_item_type_service import list_work_item_types_async


@pytest.mark.asyncio
async def test_generic_taskbot_defaults_to_task_type(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")

    task_id = await task_service.create_task_async(
        101, "Generic task", "medium", "", "", ""
    )

    task = await task_service.get_task_by_id_async(task_id)
    assert task["work_item_type"] == "task"


@pytest.mark.asyncio
async def test_clinic_profile_can_create_patient_and_session_types(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")

    patient_id = await task_service.create_task_async(
        202, "Ali Rezaei", "medium", "", "", "", work_item_type="patient"
    )
    session_id = await task_service.create_task_async(
        202, "First visit", "medium", "", "", "", work_item_type="session"
    )

    assert (await task_service.get_task_by_id_async(patient_id))["work_item_type"] == "patient"
    assert (await task_service.get_task_by_id_async(session_id))["work_item_type"] == "session"

    types = await list_work_item_types_async("clinic")
    assert {item["key"] for item in types} == {"task", "patient", "session"}
    patient = next(item for item in types if item["key"] == "patient")
    assert patient["is_default"] is True
    assert patient["allowed_child_types"] == ["session"]


@pytest.mark.asyncio
async def test_clinic_keeps_legacy_task_type_valid(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")

    task_id = await task_service.create_task_async(
        206, "Operational task", "medium", "", "", "", work_item_type="task"
    )

    assert (await task_service.get_task_by_id_async(task_id))["work_item_type"] == "task"


@pytest.mark.asyncio
async def test_clinic_default_type_is_patient(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")

    task_id = await task_service.create_task_async(
        203, "Default clinic record", "medium", "", "", ""
    )

    assert (await task_service.get_task_by_id_async(task_id))["work_item_type"] == "patient"


@pytest.mark.asyncio
async def test_invalid_work_item_type_is_rejected_for_profile(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")

    with pytest.raises(ValueError, match="invalid_work_item_type"):
        await task_service.create_task_async(
            204, "Invalid record", "medium", "", "", "", work_item_type="order"
        )


@pytest.mark.asyncio
async def test_work_item_type_filter_is_applied(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")

    await task_service.create_task_async(
        205, "Patient A", "medium", "", "", "", work_item_type="patient"
    )
    await task_service.create_task_async(
        205, "Visit A", "medium", "", "", "", work_item_type="session"
    )

    patients = await task_service.get_all_user_tasks_async(
        205, work_item_type="patient"
    )
    sessions = await task_service.get_all_user_tasks_async(
        205, work_item_type="session"
    )

    assert [item["work_item_type"] for item in patients] == ["patient"]
    assert [item["work_item_type"] for item in sessions] == ["session"]


@pytest.mark.asyncio
async def test_legacy_task_schema_migration_backfills_task_type():
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.executescript(
            """
            CREATE TABLE tasks (id TEXT PRIMARY KEY);
            INSERT INTO tasks(id) VALUES ('legacy-1');
            CREATE TABLE task_comments (id INTEGER PRIMARY KEY AUTOINCREMENT);
            """
        )

        await database.migrate_core_schema(conn)

        async with conn.execute("PRAGMA table_info(tasks)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        assert "work_item_type" in columns

        async with conn.execute(
            "SELECT work_item_type FROM tasks WHERE id='legacy-1'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] == "task"
    finally:
        await conn.close()
