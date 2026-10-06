import pytest

from services import task_query_service as query
from services import task_service
from services import task_attribute_service as attrs


@pytest.mark.asyncio
async def test_sql_task_query_filters_and_paginates(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    monkeypatch.setattr(attrs, "_bot", lambda: "clinic")
    first = await task_service.create_task_async(30, "Ali", "high", "", "", "", work_item_type="patient")
    await task_service.create_task_async(30, "Sara", "low", "", "", "", work_item_type="patient")
    await attrs.create_attribute_definition_async("doctor", "Doctor", "text", work_item_type="patient")
    await attrs.set_task_attribute_async(first, "doctor", "Dr A", 30)
    rows = await query.query_tasks_async(30, attribute_filters={"doctor": "Dr A"}, limit=1)
    assert [row["id"] for row in rows] == [first]
