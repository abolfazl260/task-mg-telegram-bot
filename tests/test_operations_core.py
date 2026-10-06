from __future__ import annotations

from typing import ClassVar

import pytest

from services import database
from services.operations.access import WorkspaceScope
from services.operations.service import (
    OperationsConfig,
    create_action,
    create_case,
    create_reference,
    create_unit,
    create_workspace,
    set_membership,
)


class SalesScope(WorkspaceScope):
    ROLE_PERMISSIONS: ClassVar[dict[str, set[str]]] = {
        "owner": {
            "units.manage",
            "memberships.manage",
            "references.manage",
            "references.view",
            "cases.manage",
            "cases.view",
            "tasks.manage",
            "tasks.view",
        },
        "sales_rep": {
            "references.view",
            "cases.view",
            "tasks.view",
            "tasks.manage",
        },
    }


@pytest.mark.asyncio
async def test_core_operations_support_non_healthcare_vertical(test_db):
    config = OperationsConfig(
        workspace_type="sales",
        reference_type="lead",
        default_timezone="UTC",
        outcomes={
            "won": ("Won", False, True),
            "follow_up": ("Follow up", True, False),
        },
    )
    workspace_id = await create_workspace(
        "100",
        "sales_bot",
        "North America Sales",
        config=config,
    )
    scope = SalesScope(workspace_id, "100")
    unit_id = await create_unit(
        scope,
        "Toronto",
        unit_type="territory",
    )
    await set_membership(
        scope,
        "200",
        "sales_rep",
        unit_id=unit_id,
    )
    reference = await create_reference(
        scope,
        unit_id,
        "Acme Inc.",
        reference_type=config.reference_type,
        external_reference="CRM-42",
        primary_owner_user_id="200",
    )
    case = await create_case(
        scope,
        reference["id"],
        "Enterprise opportunity",
        "200",
        case_type="sales_opportunity",
        primary_owner_user_id="200",
    )
    task = await create_action(
        scope,
        case["id"],
        "Prepare proposal",
        "200",
        "2026-10-15T12:00:00Z",
    )

    assert reference["reference_type"] == "lead"
    assert case["reference_id"] == reference["id"]
    assert task["workspace_id"] == workspace_id
    assert task["unit_id"] == unit_id
    assert task["reference_id"] == reference["id"]

    db = await database.get_db()
    async with db.conn.execute(
        "SELECT role FROM workspace_memberships "
        "WHERE workspace_id=? AND user_id='200'",
        (workspace_id,),
    ) as cur:
        assert (await cur.fetchone())[0] == "sales_rep"

    async with db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'clinic_%'"
    ) as cur:
        assert await cur.fetchall() == []
