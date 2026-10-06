from __future__ import annotations

import pytest

from services import task_attribute_service as attributes
from services import task_service
from services.database import fetch_all


@pytest.mark.asyncio
async def test_typed_attribute_definition_and_values(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    monkeypatch.setattr(attributes, "_bot", lambda: "clinic")
    patient = await task_service.create_task_async(
        10, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    definition = await attributes.create_attribute_definition_async(
        "medical_history", "Medical history", "long_text", work_item_type="patient",
        required=True, searchable=True, filterable=True, group_key="clinical",
    )
    assert definition["version"] == 1
    rows = await attributes.set_task_attribute_async(
        patient, "medical_history", "Asthma", 10
    )
    assert rows[0]["value"] == "Asthma"
    assert (await attributes.validate_required_attributes_async(patient, 10)) == []


@pytest.mark.asyncio
async def test_attribute_validation_defaults_enums_and_versioning(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    monkeypatch.setattr(attributes, "_bot", lambda: "clinic")
    patient = await task_service.create_task_async(
        11, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    first = await attributes.create_attribute_definition_async(
        "priority", "Priority", "select", work_item_type="patient",
        default="normal", validation={"enum": ["normal", "urgent"]}, required=True,
    )
    second = await attributes.create_attribute_definition_async(
        "priority", "Priority", "select", work_item_type="patient",
        validation={"enum": ["normal", "urgent", "critical"]}, required=True,
    )
    assert (await attributes.get_attribute_definition_async(first["id"]))["active"] == 0
    assert second["version"] == 2
    with pytest.raises(ValueError, match="invalid_attribute_enum_value"):
        await attributes.set_task_attribute_async(patient, "priority", "low", 11)
    assert "priority" in await attributes.validate_required_attributes_async(patient, 11)
    await attributes.set_task_attribute_async(patient, "priority", "urgent", 11)
    assert "priority" not in await attributes.validate_required_attributes_async(patient, 11)


@pytest.mark.asyncio
async def test_attribute_permission_and_repeatable_multi_select(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    monkeypatch.setattr(attributes, "_bot", lambda: "clinic")
    patient = await task_service.create_task_async(
        12, "Patient", "medium", "", "", "", work_item_type="patient"
    )
    await attributes.create_attribute_definition_async(
        "tags", "Tags", "multi_select", work_item_type="patient",
        repeatable=False, validation={"enum": ["a", "b", "c"]},
    )
    await attributes.set_task_attribute_async(patient, "tags", ["a", "b"], 12)
    with pytest.raises(PermissionError, match="attribute_permission_denied"):
        await attributes.get_task_attributes_async(patient, 99)


@pytest.mark.asyncio
async def test_sensitive_attribute_roles_and_audit_metadata(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "clinic")
    monkeypatch.setattr(attributes, "_bot", lambda: "clinic")
    patient = await task_service.create_task_async(13, "Patient", "medium", "", "", "", work_item_type="patient")
    await attributes.create_attribute_definition_async(
        "diagnosis", "Diagnosis", "text", work_item_type="patient", sensitive=True,
        view_roles=["doctor"], edit_roles=["doctor"],
    )
    await attributes.set_task_attribute_async(patient, "diagnosis", "private", 13)
    assert (await attributes.get_task_attributes_async(patient, 13))[0]["sensitive"] is True
    audit = await fetch_all("task_attribute_audit", "task_id=?", (patient,))
    assert audit and "private" not in str(audit[0])
