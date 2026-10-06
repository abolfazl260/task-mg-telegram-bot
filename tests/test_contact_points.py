from __future__ import annotations

import pytest

from services import contact_point_service as contacts
from services import task_service


@pytest.mark.asyncio
async def test_contact_points_support_multiple_primary_and_normalized_search(test_db):
    task = await task_service.create_task_async(20, "Patient", "medium", "", "", "")
    first = await contacts.create_contact_point_async(task, "phone", "۰۹۱۲ ۱۲۳ ۴۵۶۷", 20, label="mobile", is_primary=True)
    second = await contacts.create_contact_point_async(task, "phone", "+98 912 999 0000", 20, label="work", is_primary=True)
    rows = await contacts.list_contact_points_async(task, 20)
    assert len(rows) == 2
    assert [r["is_primary"] for r in rows if r["type"] == "phone"] == [1, 0]
    assert first["normalized_value"] == "09121234567"
    assert len(await contacts.search_contact_points_async("0912-999-0000", 20, contact_type="phone")) == 1
    assert second["label"] == "work"


@pytest.mark.asyncio
async def test_contact_points_duplicate_and_permission_isolation(test_db):
    task = await task_service.create_task_async(21, "Patient", "medium", "", "", "")
    await contacts.create_contact_point_async(task, "email", "Test@Example.com", 21)
    with pytest.raises(ValueError, match="duplicate_contact_point"):
        await contacts.create_contact_point_async(task, "email", " test@example.com ", 21)
    with pytest.raises(PermissionError, match="contact_point_permission_denied"):
        await contacts.list_contact_points_async(task, 22)


@pytest.mark.asyncio
async def test_contact_points_can_be_inactivated_without_data_loss(test_db):
    task = await task_service.create_task_async(23, "Patient", "medium", "", "", "")
    point = await contacts.create_contact_point_async(task, "phone", "+1 555 100", 23)
    await contacts.update_contact_point_async(point["id"], 23, status="inactive")
    assert await contacts.list_contact_points_async(task, 23) == []
    assert len(await contacts.list_contact_points_async(task, 23, include_inactive=True)) == 1
