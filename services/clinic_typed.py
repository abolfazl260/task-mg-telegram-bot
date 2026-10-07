"""Typed Patient/Session/Follow-up adapter for the Clinic vertical.

The persistence boundary remains the Core ``tasks`` hierarchy. Operational
metadata stays in ``typed_work_item_data``, while configurable medical fields
are persisted through the Core Attribute Engine so field-level permissions,
validation and audit are enforced consistently across channels.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from services import task_attribute_service as attributes
from services.database import execute, fetch_all_sql, fetch_one_sql, transaction
from services.healthcare.access import ClinicAccessError, Scope
from services.operations.service import audit, now, text, utc_date
from services.work_item_access import authorized_task, field_allowed
from services.work_item_type_service import validate_work_item_type_async

SESSION_STATUSES = {"scheduled", "completed", "cancelled", "no_show", "rescheduled"}
FOLLOWUP_STATUSES = {"due", "in_progress", "completed", "closed", "rescheduled"}

MEDICAL_ATTRIBUTE_KEYS = frozenset({
    "disease_history",
    "chronic_conditions",
    "allergies",
    "medications",
    "diagnoses",
    "clinical_notes",
    "treatment_information",
})


def _json(value):
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False, separators=(",", ":"))


def _parse(value):
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


async def _save_data(task_id: str, data: dict[str, Any]) -> None:
    stamp = now()
    await execute("""INSERT INTO typed_work_item_data(task_id,data_json,created_at,updated_at)
        VALUES(?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET data_json=excluded.data_json,updated_at=excluded.updated_at""", (task_id, _json(data), stamp, stamp))


def _without_medical(data: dict[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (data or {}).items() if key not in MEDICAL_ATTRIBUTE_KEYS}


def _split_fields(fields: dict | None) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata, medical = {}, {}
    for key, value in (fields or {}).items():
        (medical if key in MEDICAL_ATTRIBUTE_KEYS else metadata)[key] = value
    return metadata, medical


async def _preflight_medical_fields(task: dict, actor_id: str, values: dict[str, Any]) -> dict[str, dict]:
    definitions = {}
    for key, value in values.items():
        definition = await fetch_one_sql(
            """SELECT * FROM task_attribute_definitions
               WHERE bot_key=? AND workspace_id IS ? AND work_item_type=?
                 AND field_key=? AND active=1
               ORDER BY version DESC LIMIT 1""",
            (task.get("bot_key") or "default", task.get("workspace_id"),
             task.get("work_item_type") or "task", key),
        )
        if not definition:
            raise ValueError("attribute_definition_not_found")
        if not await field_allowed(definition, task, actor_id, action="edit"):
            raise PermissionError("attribute_field_edit_denied")
        await attributes.validate_attribute_value_async(
            value,
            definition["data_type"],
            _parse(definition.get("validation_json")),
            allow_none=not bool(definition.get("required")),
        )
        definitions[key] = definition
    return definitions


async def _write_medical_attributes(task_id: str, actor_id: str, values: dict[str, Any], definitions: dict[str, dict]) -> None:
    for key, value in values.items():
        await attributes.set_task_attribute_async(
            task_id, key, value, actor_id, definition_id=definitions[key]["id"]
        )


async def _legacy_medical_projection(task: dict, actor_id: str, raw: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Read old embedded medical values only through the active field permission."""
    result = dict(current)
    for key in MEDICAL_ATTRIBUTE_KEYS:
        if key in result or raw.get(key) in (None, ""):
            continue
        definition = await fetch_one_sql(
            """SELECT * FROM task_attribute_definitions
               WHERE bot_key=? AND workspace_id IS ? AND work_item_type=?
                 AND field_key=? AND active=1
               ORDER BY version DESC LIMIT 1""",
            (task.get("bot_key") or "default", task.get("workspace_id"),
             task.get("work_item_type") or "task", key),
        )
        if definition and await field_allowed(definition, task, actor_id, action="view"):
            result[key] = raw[key]
    return result


async def _item(task_id: str, actor_id: str, *, write=False) -> dict:
    task = await authorized_task(task_id, actor_id, write=write)
    data = await fetch_one_sql("SELECT data_json FROM typed_work_item_data WHERE task_id=?", (str(task_id),))
    raw = _parse(data.get("data_json") if data else "{}")
    attribute_rows = await attributes.get_task_attributes_async(task_id, actor_id)
    medical = {
        row["field_key"]: row.get("value")
        for row in attribute_rows
        if row.get("field_key") in MEDICAL_ATTRIBUTE_KEYS
    }
    medical = await _legacy_medical_projection(task, actor_id, raw, medical)
    task["attributes"] = attribute_rows
    task["medical_attributes"] = medical
    # Backward-compatible read projection: permitted medical values remain
    # available under typed, but they are no longer persisted there.
    task["typed"] = {**_without_medical(raw), **medical}
    return task


async def _validate_branch(scope: Scope, branch_id: str, permission: str):
    return await scope.branch(branch_id, permission)


async def create_patient_async(scope: Scope, branch_id: str, display_name: str, *, doctor_id: str | None = None, reference_id: str | None = None, patient_id: str | None = None, fields: dict | None = None) -> dict:
    await _validate_branch(scope, branch_id, "patients.manage")
    if doctor_id:
        await fetch_one_sql("SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' AND (unit_id IS NULL OR unit_id=?)", (scope.workspace_id, str(doctor_id), branch_id)) or (_ for _ in ()).throw(ClinicAccessError("forbidden"))
    ws = await fetch_one_sql("SELECT bot_key FROM workspaces WHERE id=?", (scope.workspace_id,))
    bot = ws["bot_key"]
    task_id = uuid.uuid4().hex
    external_patient_id = text(patient_id, max_length=100) if patient_id not in (None, "") else reference_id
    metadata_fields, medical_fields = _split_fields(fields)
    task_context = {
        "bot_key": bot,
        "workspace_id": scope.workspace_id,
        "unit_id": branch_id,
        "work_item_type": "patient",
        "user_id": str(scope.actor_id),
    }
    medical_definitions = await _preflight_medical_fields(
        task_context, str(scope.actor_id), medical_fields
    ) if medical_fields else {}
    payload = dict(metadata_fields)
    payload.update({"patient_id": external_patient_id, "doctor_id": doctor_id, "status": "active"})
    await transaction([
        ("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (str(scope.actor_id),)),
        ("INSERT INTO tasks(id,bot_key,work_item_type,user_id,title,status,created_at,workspace_id,unit_id,reference_id,assignee_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (task_id, bot, "patient", str(scope.actor_id), text(display_name, max_length=200), "pending", now(), scope.workspace_id, branch_id, reference_id, str(doctor_id) if doctor_id else None)),
        ("INSERT INTO typed_work_item_data(task_id,data_json,created_at,updated_at) VALUES(?,?,?,?)", (task_id, _json(payload), now(), now())),
        audit(scope, branch_id, "patient.created", "task", task_id),
    ])
    if medical_fields:
        await _write_medical_attributes(task_id, str(scope.actor_id), medical_fields, medical_definitions)
    return await _item(task_id, str(scope.actor_id))


async def create_child_async(scope: Scope, parent_task_id: str, item_type: str, title: str, *, scheduled_at: str | None = None, doctor_id: str | None = None, branch_id: str | None = None, fields: dict | None = None) -> dict:
    parent = await authorized_task(parent_task_id, str(scope.actor_id), write=True, workspace_id=scope.workspace_id)
    if parent.get("work_item_type") not in {"patient", "session", "case"}:
        raise ValueError("parent_must_be_patient_or_session")
    if branch_id and branch_id != parent.get("unit_id"):
        raise ValueError("branch_scope_mismatch")
    await _validate_branch(scope, parent["unit_id"], "tasks.manage")
    item_type = str(item_type).strip().lower()
    # Follow-up and action are internal Clinic children, not profile creation types.
    if item_type not in {"followup", "action", "case"}:
        item_type = await validate_work_item_type_async(item_type, parent["bot_key"])
    if item_type not in {"session", "followup", "action", "case"}:
        raise ValueError("invalid_clinic_child_type")
    item_id = uuid.uuid4().hex
    metadata_fields, medical_fields = _split_fields(fields)
    payload = dict(metadata_fields)
    if item_type == "followup" and payload.get("dedupe_key"):
        existing_rows = await fetch_all_sql("SELECT t.*,d.data_json FROM tasks t JOIN typed_work_item_data d ON d.task_id=t.id WHERE t.workspace_id=? AND t.parent_task_id=? AND t.work_item_type='followup' AND t.archived_at IS NULL", (scope.workspace_id, parent_task_id))
        for existing in existing_rows:
            if _parse(existing.get("data_json")).get("dedupe_key") == str(payload["dedupe_key"]):
                return await _item(existing["id"], str(scope.actor_id))
    if scheduled_at:
        payload["scheduled_at"] = utc_date(scheduled_at)
    if doctor_id:
        payload["doctor_id"] = str(doctor_id)
    payload.setdefault("status", "scheduled" if item_type == "session" else "due")
    status = payload["status"]
    if item_type == "session" and status not in SESSION_STATUSES: raise ValueError("invalid_session_status")
    if item_type == "followup" and status not in FOLLOWUP_STATUSES: raise ValueError("invalid_followup_status")
    task_context = {
        "bot_key": parent["bot_key"],
        "workspace_id": scope.workspace_id,
        "unit_id": parent["unit_id"],
        "work_item_type": item_type,
        "user_id": str(scope.actor_id),
    }
    medical_definitions = await _preflight_medical_fields(
        task_context, str(scope.actor_id), medical_fields
    ) if medical_fields else {}
    await transaction([
        ("INSERT INTO tasks(id,bot_key,work_item_type,parent_task_id,user_id,title,status,deadline,created_at,workspace_id,unit_id,reference_id,assignee_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (item_id, parent["bot_key"], item_type, parent_task_id, str(scope.actor_id), text(title, max_length=500), status, payload.get("scheduled_at") or payload.get("due_at") or "", now(), scope.workspace_id, parent["unit_id"], parent.get("reference_id"), str(doctor_id) if doctor_id else None)),
        ("INSERT INTO typed_work_item_data(task_id,data_json,created_at,updated_at) VALUES(?,?,?,?)", (item_id, _json(payload), now(), now())),
        audit(scope, parent["unit_id"], f"{item_type}.created", "task", item_id),
    ])
    if medical_fields:
        await _write_medical_attributes(item_id, str(scope.actor_id), medical_fields, medical_definitions)
    return await _item(item_id, str(scope.actor_id))


async def list_children_async(parent_task_id: str, actor_id: str, *, item_type: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    await authorized_task(parent_task_id, actor_id)
    clauses = ["t.parent_task_id=?", "t.archived_at IS NULL"]
    params: list[Any] = [str(parent_task_id)]
    if item_type: clauses.append("t.work_item_type=?"); params.append(str(item_type))
    if status: clauses.append("t.status=?"); params.append(str(status))
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    count = await fetch_one_sql("SELECT COUNT(*) AS n FROM tasks t WHERE " + " AND ".join(clauses), tuple(params))
    rows = await fetch_all_sql("SELECT t.*,d.data_json FROM tasks t LEFT JOIN typed_work_item_data d ON d.task_id=t.id WHERE " + " AND ".join(clauses) + " ORDER BY COALESCE(t.deadline,t.created_at),t.id LIMIT ? OFFSET ?", tuple(params) + (limit, offset))
    for row in rows:
        # Lists never surface embedded legacy medical values; sensitive fields
        # are loaded only on the permission-aware detail path.
        row["typed"] = _without_medical(_parse(row.pop("data_json", "{}")))
    return {"items": rows, "total": int((count or {}).get("n") or 0), "limit": limit, "offset": offset}


async def transition_async(task_id: str, actor_id: str, status: str, *, fields: dict | None = None) -> dict:
    item = await _item(task_id, actor_id, write=True)
    item_type = item.get("work_item_type")
    allowed = SESSION_STATUSES if item_type == "session" else FOLLOWUP_STATUSES if item_type == "followup" else {"pending", "in_progress", "done", "cancelled"}
    if status not in allowed: raise ValueError("invalid_child_status")
    metadata_fields, medical_fields = _split_fields(fields)
    medical_definitions = await _preflight_medical_fields(
        item, actor_id, medical_fields
    ) if medical_fields else {}
    payload = _without_medical(item["typed"])
    payload.update(metadata_fields)
    payload["status"] = status
    await transaction([("UPDATE tasks SET status=?,completed_at=? WHERE id=?", (status, now() if status in {"completed", "done"} else "", task_id)), ("INSERT INTO operational_audit(id,workspace_id,unit_id,actor_user_id,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, item["workspace_id"], item["unit_id"], str(actor_id), f"{item_type}.status_changed", "task", task_id, now()))])
    await _save_data(task_id, payload)
    if medical_fields:
        await _write_medical_attributes(task_id, actor_id, medical_fields, medical_definitions)
    return await _item(task_id, actor_id)


async def reschedule_async(task_id: str, actor_id: str, scheduled_at: str) -> dict:
    item = await _item(task_id, actor_id, write=True)
    if item.get("work_item_type") != "session": raise ValueError("not_session")
    when = utc_date(scheduled_at); return await transition_async(task_id, actor_id, "rescheduled", fields={"scheduled_at": when, "rescheduled_from": item.get("typed", {}).get("scheduled_at")})



async def update_item_async(task_id: str, actor_id: str, *, title: str | None = None, fields: dict | None = None) -> dict:
    item = await _item(task_id, actor_id, write=True)
    metadata_fields, medical_fields = _split_fields(fields)
    medical_definitions = await _preflight_medical_fields(
        item, actor_id, medical_fields
    ) if medical_fields else {}
    updates = []
    params = []
    if title is not None:
        value = text(title, max_length=500)
        updates.extend(['title=?']); params.append(value)
    if updates:
        params.append(task_id); await execute('UPDATE tasks SET ' + ','.join(updates) + ' WHERE id=?', tuple(params))
    if metadata_fields:
        payload = _without_medical(item['typed'])
        payload.update(metadata_fields)
        await _save_data(task_id, payload)
    elif medical_fields:
        # Clean up medical keys left by the pre-Attribute implementation.
        await _save_data(task_id, _without_medical(item['typed']))
    if medical_fields:
        await _write_medical_attributes(task_id, actor_id, medical_fields, medical_definitions)
    return await _item(task_id, actor_id)



async def assign_async(task_id: str, actor_id: str, target_user_id: str) -> dict:
    item = await _item(task_id, actor_id, write=True)
    target = await fetch_one_sql("SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' AND (unit_id IS NULL OR unit_id=?)", (item['workspace_id'], str(target_user_id), item.get('unit_id')))
    if not target:
        raise ValueError('invalid_staff_scope')
    await execute("UPDATE tasks SET assignee_id=? WHERE id=?", (str(target_user_id), task_id))
    payload = _without_medical(item['typed']); payload['owner_id'] = str(target_user_id); payload['assigned_at'] = now(); await _save_data(task_id, payload)
    await execute("INSERT INTO operational_audit(id,workspace_id,unit_id,actor_user_id,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, item['workspace_id'], item['unit_id'], str(actor_id), f"{item['work_item_type']}.assigned", 'task', task_id, now()))
    return await _item(task_id, actor_id)


async def create_next_followup_async(scope: Scope, source_task_id: str, title: str, *, due_at: str, owner_id: str | None = None, dedupe_key: str | None = None) -> dict:
    source = await _item(source_task_id, str(scope.actor_id), write=True)
    parent_id = source['parent_task_id'] or source['id']
    return await create_child_async(scope, parent_id, 'followup', title, fields={'due_at': due_at, 'source_session_id': source_task_id, 'owner_id': owner_id, 'dedupe_key': dedupe_key} if dedupe_key else {'due_at': due_at, 'source_session_id': source_task_id, 'owner_id': owner_id})

def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)

create_patient = lambda *a, **k: _run(create_patient_async(*a, **k))
create_child = lambda *a, **k: _run(create_child_async(*a, **k))
list_children = lambda *a, **k: _run(list_children_async(*a, **k))
transition = lambda *a, **k: _run(transition_async(*a, **k))
reschedule = lambda *a, **k: _run(reschedule_async(*a, **k))
assign = lambda *a, **k: _run(assign_async(*a, **k))
create_next_followup = lambda *a, **k: _run(create_next_followup_async(*a, **k))
update_item = lambda *a, **k: _run(update_item_async(*a, **k))
