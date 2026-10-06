import pytest

from services import task_service
from services import view_schema_service as views


@pytest.mark.asyncio
async def test_versioned_view_schema_validation(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    monkeypatch.setattr(views, "_bot", lambda: "clinic")
    schema = {"sections": [{"key": "identity", "label": "Identity", "fields": [{"field_key": "medical_history"}]}], "responsive": {"mobile": "stack"}}
    first = await views.save_view_schema_async(schema, work_item_type="patient", schema_kind="detail")
    second = await views.save_view_schema_async(schema, work_item_type="patient", schema_kind="detail")
    assert first["version"] == 1 and second["version"] == 2
    assert (await views.get_view_schema_async(work_item_type="patient", schema_kind="detail"))["schema"]["sections"][0]["key"] == "identity"
    with pytest.raises(ValueError, match="duplicate_view_schema_field"):
        await views.save_view_schema_async({"sections": [{"key": "x", "fields": [{"field_key": "a"}, {"field_key": "a"}]}]}, work_item_type="patient")
