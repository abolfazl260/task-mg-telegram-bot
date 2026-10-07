"""Synthetic clinic fixtures only; tests exercise real SQLite and domain services."""

import asyncio
import copy
import json
import sqlite3
from datetime import datetime, timezone

import aiosqlite
import pytest

from services import database, task_service
from services.healthcare import followups, service, workflows
from services.healthcare.access import ClinicAccessError, Scope
from services.operations.schema import migrate as migrate_operations


async def test_patient_has_multiple_cases_and_tasks(clinic):
    scope = clinic["owner"]
    second = await service.create_case(scope, clinic["pa"]["id"], "Second journey", "2")
    t1 = await service.create_action(
        scope, clinic["ca"]["id"], "Call", "3", "2026-10-06T10:00:00+03:30"
    )
    t2 = await service.create_action(
        scope, second["id"], "Review", "2", "2026-10-07T10:00:00Z"
    )
    assert t1["patient_id"] == t2["patient_id"]
    assert t1["case_id"] != t2["case_id"]
    assert t1["deadline"] == "2026-10-06T06:30:00Z"
    assert (await service.get_entity(scope, "cases", clinic["ca"]["id"]))[
        "next_action_task_id"
    ] == t1["id"]


async def test_scope_enforced_in_queries_and_valid_id_access(clinic):
    reception = Scope(clinic["owner"].organization_id, "2")
    page = await service.list_entities(reception, "patients", limit=1)
    assert page["total"] == 1 and page["items"][0]["id"] == clinic["pa"]["id"]
    assert (await service.list_entities(reception, "patients", branch_id=clinic["b"]))[
        "total"
    ] == 0
    for kind, ident in [
        ("patients", clinic["pb"]["id"]),
        ("cases", clinic["cb"]["id"]),
    ]:
        with pytest.raises(ClinicAccessError):
            await service.get_entity(reception, kind, ident)
        with pytest.raises(ClinicAccessError):
            await service.get_entity(reception, kind, ident, manage=True)
    other = await service.create_organization("9", "clinic", "Other clinic")
    with pytest.raises(ClinicAccessError):
        await service.get_entity(Scope(other, "9"), "patients", clinic["pa"]["id"])
    assert (
        await service.list_entities(
            Scope(clinic["owner"].organization_id, "7"), "patients"
        )
    )["total"] == 2


async def test_patient_search_uses_core_reference_fields_and_preserves_scope(clinic):
    scope = clinic["owner"]
    patient = await service.create_patient(
        scope,
        clinic["a"],
        "Searchable Patient",
        external_reference="SEARCH-001",
        phone="+98 912 345 6789",
    )
    reception = Scope(scope.organization_id, "2")

    for query in ("Searchable", "SEARCH-001", "345 6789"):
        page = await service.list_entities(
            reception, "patients", search=query, limit=20
        )
        assert patient["id"] in {item["id"] for item in page["items"]}

    hidden = await service.list_entities(
        reception, "patients", search="Synthetic B", limit=20
    )
    assert clinic["pb"]["id"] not in {item["id"] for item in hidden["items"]}


async def test_doctor_context_is_independent_from_task_owner(clinic):
    task = await service.create_action(
        clinic["owner"],
        clinic["ca"]["id"],
        "Assigned to coordinator",
        "3",
        "2026-10-07T10:00:00Z",
    )
    doctor = Scope(clinic["owner"].organization_id, "4")
    assert (await service.get_entity(doctor, "tasks", task["id"]))["assignee_id"] == "3"
    with pytest.raises(ClinicAccessError):
        await service.get_entity(
            Scope(doctor.organization_id, "8"), "tasks", task["id"]
        )
    with pytest.raises(ClinicAccessError):
        await service.get_entity(
            Scope(doctor.organization_id, "8"), "patients", clinic["pa"]["id"]
        )


async def test_invalid_owner_and_cross_branch_links_rejected(clinic, test_db):
    scope = clinic["owner"]
    with pytest.raises(ValueError, match="invalid_staff_scope"):
        await service.create_action(
            scope, clinic["ca"]["id"], "Invalid owner", "6", "2026-10-07T10:00:00Z"
        )
    tid = service.new_id()
    with pytest.raises(sqlite3.IntegrityError):
        await database.execute(
            "INSERT INTO tasks(id,user_id,title,workspace_id,unit_id,reference_id,case_id) VALUES(?,?,?,?,?,?,?)",
            (
                tid,
                "1",
                "Invalid link",
                scope.organization_id,
                clinic["a"],
                clinic["pb"]["id"],
                clinic["cb"]["id"],
            ),
        )
    await test_db.conn.rollback()
    assert (
        await database.fetch_one_sql("SELECT * FROM tasks WHERE id=?", (tid,)) is None
    )


async def test_revoked_membership_denies_access_and_owner_assignment(clinic):
    scope = clinic["owner"]
    await service.set_membership(scope, "2", "reception", clinic["a"], active=False)
    with pytest.raises(ClinicAccessError):
        await service.get_entity(
            Scope(scope.organization_id, "2"), "patients", clinic["pa"]["id"]
        )
    with pytest.raises(ValueError):
        await service.create_action(
            scope, clinic["ca"]["id"], "No revoked owner", "2", "2026-10-07T10:00:00Z"
        )
    with pytest.raises(ClinicAccessError):
        await service.set_membership(Scope(scope.organization_id, "7"), "2", "owner")


async def test_followup_requires_outcome_next_action_and_is_idempotent(clinic):
    scope = clinic["owner"]
    f = await followups.create_followup(
        scope, clinic["ca"]["id"], "3", "2026-10-06T10:00:00Z"
    )
    with pytest.raises(ValueError, match="followup_outcome_required"):
        await service.set_task_status(scope, f["task_id"], "done")
    with pytest.raises(ValueError, match="next_action_required"):
        await followups.record_outcome(scope, f["id"], "no_answer")
    assert (await service.get_entity(scope, "tasks", f["task_id"]))[
        "status"
    ] == "pending"
    results = await asyncio.gather(
        *[
            followups.record_outcome(
                scope, f["id"], "no_answer", next_due_at="2026-10-07T10:00:00Z"
            )
            for _ in range(5)
        ]
    )
    successor_ids = {r["next_followup_id"] for r in results}
    assert len(successor_ids) == 1
    child = await service.get_entity(scope, "followups", successor_ids.pop())
    assert child["attempt_number"] == 2
    assert (await service.list_entities(scope, "followups"))["total"] == 2
    task = await service.get_entity(scope, "tasks", f["task_id"])
    assert task["status"] == "done" and task["outcome_id"]
    assert (await service.get_entity(scope, "cases", f["case_id"]))[
        "next_action_task_id"
    ] == child["task_id"]
    await followups.record_outcome(scope, child["id"], "resolved")
    missing = await service.list_entities(scope, "cases", missing_next_action=True)
    assert f["case_id"] in {c["id"] for c in missing["items"]}


async def test_queue_clinic_timezone_pagination_and_filters(clinic):
    scope = clinic["owner"]
    # Tehran midnight is 20:30 UTC on the previous day.
    for due in ["2026-10-05T20:29:00Z", "2026-10-05T20:31:00Z", "2026-10-06T20:30:00Z"]:
        await followups.create_followup(scope, clinic["ca"]["id"], "3", due)
    await followups.create_followup(
        scope, clinic["cb"]["id"], "6", "2026-10-05T20:31:00Z"
    )
    at = datetime(2026, 10, 6, 8, tzinfo=timezone.utc)
    reception = Scope(scope.organization_id, "2")
    assert (await followups.queue(reception, "today", at=at))["total"] == 1
    assert (await followups.queue(reception, "overdue", at=at))["total"] == 2
    assert (await followups.queue(reception, "upcoming", at=at))["total"] == 1
    assert (await followups.queue(scope, "today", at=at, doctor_id="4"))["total"] == 1
    assert (await followups.queue(scope, "overdue", at=at, limit=1, offset=1))[
        "limit"
    ] == 1


async def test_legacy_task_web_reports_and_telegram_cannot_read_clinic_tasks(
    clinic, monkeypatch
):
    scope = clinic["owner"]
    f = await followups.create_followup(
        scope, clinic["ca"]["id"], "3", "2026-10-06T10:00:00Z"
    )
    raw_task = await service.get_entity(scope, "tasks", f["task_id"])
    assert await task_service.get_task_by_id_async(f["task_id"]) is None
    assert not await task_service.get_all_user_tasks_async("1")
    assert not await task_service.user_can_modify_task_async("1", raw_task)
    assert not await task_service.change_task_status_async(f["task_id"], "done", "1")
    from webapp import admin_api, tasks_api

    monkeypatch.setattr(tasks_api, "_set_context", lambda key: key)
    assert await tasks_api.get_task(1, f["task_id"], "clinic") is None
    assert not await admin_api.list_user_tasks("1")
    assert (await admin_api.dashboard_stats())["tasks"]["total"] == 0
    legacy = await task_service.create_task_async(
        "1", "Legacy task", "medium", "", "", ""
    )
    assert (await task_service.get_task_by_id_async(legacy))["title"] == "Legacy task"


@pytest.mark.parametrize("template_key", list(workflows.DEFAULT_TEMPLATES))
async def test_five_templates_pin_version_and_validate_stage(clinic, template_key):
    scope = clinic["owner"]
    seeded = await workflows.seed_defaults(scope)
    assert len(await workflows.seed_defaults(scope)) == 5
    version = next(v for v in seeded if v["template_key"] == template_key)
    definition = json.loads(version["definition_json"])
    role = definition["stages"][0]["owner_role"]
    owner = "5" if role == "assistant" else "3"
    case = await service.create_case(scope, clinic["pa"]["id"], template_key, owner)
    case = await workflows.start(scope, case["id"], version["id"], owner)
    updated = copy.deepcopy(definition)
    updated["stages"][0]["due_hours"] = 48
    newer = await workflows.publish(scope, template_key, updated)
    assert newer["version"] == 2
    instance = await database.fetch_one_sql(
        "SELECT * FROM workflow_instances WHERE id=?",
        (case["workflow_instance_id"],),
    )
    assert instance["version_id"] == version["id"]
    next_stage = definition["stages"][0]["transitions"][0]
    with pytest.raises(ValueError, match="workflow_action_pending"):
        await workflows.transition(
            scope,
            case["id"],
            next_stage,
            owner,
            expected_stage=definition["initial_stage"],
        )
    f = await database.fetch_one_sql(
        "SELECT * FROM followups WHERE task_id=?", (case["next_action_task_id"],)
    )
    await followups.record_outcome(scope, f["id"], "resolved")
    transitioned = await workflows.transition(
        scope, case["id"], next_stage, owner, expected_stage=definition["initial_stage"]
    )
    assert transitioned["current_stage"] == next_stage
    with pytest.raises(ValueError, match="workflow_stage_conflict"):
        await workflows.transition(
            scope,
            case["id"],
            next_stage,
            owner,
            expected_stage=definition["initial_stage"],
        )


async def test_workflow_unsupported_automation_rejected_and_audit_immutable(
    clinic, test_db
):
    definition = copy.deepcopy(workflows.DEFAULT_TEMPLATES["general_callback"])
    definition["stages"][0]["reminder_policy"] = "at_due"
    with pytest.raises(ValueError, match="automation_not_available"):
        await workflows.publish(clinic["owner"], "bad", definition)
    events = await database.fetch_all_sql(
        "SELECT * FROM operational_audit WHERE workspace_id=?",
        (clinic["owner"].organization_id,),
    )
    assert events and all("display_name" not in event for event in events)
    with pytest.raises(sqlite3.IntegrityError, match="immutable_audit"):
        await database.execute(
            "DELETE FROM operational_audit WHERE id=?", (events[0]["id"],)
        )
    await test_db.conn.rollback()


async def test_additive_migration_preserves_legacy_data_and_is_repeatable(tmp_path):
    path = tmp_path / "legacy.db"
    conn = await aiosqlite.connect(path)
    try:
        await conn.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '',
                timezone TEXT NOT NULL DEFAULT 'UTC',
                date_format TEXT NOT NULL DEFAULT 'jalali',
                first_seen TEXT NOT NULL DEFAULT '',
                last_seen TEXT NOT NULL DEFAULT '',
                messages_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE clinic_organizations (
                id TEXT PRIMARY KEY,
                bot_key TEXT NOT NULL,
                name TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Tehran',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                bot_key TEXT NOT NULL DEFAULT 'default',
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'pending',
                deadline TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                team_id TEXT,
                assignee_id TEXT,
                assignee_name TEXT NOT NULL DEFAULT '',
                assignee_username TEXT NOT NULL DEFAULT '',
                jira_key TEXT NOT NULL DEFAULT '',
                jira_sync_hash TEXT NOT NULL DEFAULT '',
                organization_id TEXT,
                branch_id TEXT,
                patient_id TEXT,
                case_id TEXT,
                outcome_id TEXT,
                workflow_instance_id TEXT
            );
            """
        )
        await conn.execute("INSERT INTO users(user_id) VALUES('legacy')")
        await conn.execute(
            "INSERT INTO clinic_organizations(id,bot_key,name) "
            "VALUES('legacy-workspace','clinic','Legacy clinic')"
        )
        await conn.execute(
            "INSERT INTO tasks(id,user_id,title,organization_id) "
            "VALUES('old','legacy','Existing task','legacy-workspace')"
        )
        await conn.commit()

        for _ in range(2):
            await migrate_operations(conn)

        async with conn.execute(
            "SELECT title,workspace_id FROM tasks WHERE id='old'"
        ) as cur:
            assert tuple(await cur.fetchone()) == (
                "Existing task",
                "legacy-workspace",
            )
        async with conn.execute(
            "SELECT name,workspace_type FROM workspaces "
            "WHERE id='legacy-workspace'"
        ) as cur:
            assert tuple(await cur.fetchone()) == ("Legacy clinic", "healthcare")
        async with conn.execute("PRAGMA foreign_key_check") as cur:
            assert not await cur.fetchall()
    finally:
        await conn.close()


async def test_task_outcome_is_independent_from_task_status(clinic):
    scope = clinic["owner"]
    task = await service.create_action(
        scope, clinic["ca"]["id"], "Operational action", "3", "2026-10-07T10:00:00Z"
    )
    result = await service.record_task_outcome(scope, task["id"], "resolved")
    assert result["status"] == "pending" and result["outcome_id"]
    done = await service.set_task_status(scope, task["id"], "done")
    assert done["outcome_id"] == result["outcome_id"]


async def test_raw_completion_cannot_bypass_required_outcome(clinic, test_db):
    f = await followups.create_followup(
        clinic["owner"], clinic["ca"]["id"], "3", "2026-10-07T10:00:00Z"
    )
    with pytest.raises(sqlite3.IntegrityError, match="followup_outcome_required"):
        await database.execute(
            "UPDATE tasks SET status='done' WHERE id=?", (f["task_id"],)
        )
    await test_db.conn.rollback()


async def test_patient_archival_preserves_links_and_prevents_new_cases(clinic):
    scope = clinic["owner"]
    patient = await service.update_patient(scope, clinic["pa"]["id"], archive=True)
    assert patient["status"] == "archived"
    with pytest.raises(ValueError, match="patient_is_archived"):
        await service.create_case(scope, patient["id"], "New", "3")
    assert (await service.get_entity(scope, "cases", clinic["ca"]["id"]))[
        "patient_id"
    ] == patient["id"]
