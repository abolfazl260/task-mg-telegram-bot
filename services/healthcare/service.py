"""Scoped operational patient/case/action repositories and atomic mutations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.database import fetch_all_sql, fetch_one_sql, transaction
from services.healthcare.access import ROLE_PERMISSIONS, ClinicAccessError, Scope
from services.healthcare.terminology import to_healthcare_record

CASE_STATUSES = {"active", "waiting", "blocked", "completed", "closed", "cancelled"}
OUTCOMES = {
    "reached": ("ارتباط برقرار شد", False, True),
    "no_answer": ("جواب نداد", True, False),
    "scheduled": ("زمان‌بندی شد", True, False),
    "needs_time": ("زمان بیشتری لازم است", True, False),
    "declined": ("انصراف", False, True),
    "escalated": ("نیاز به بررسی مسئول", True, False),
    "closed": ("بسته شد", False, True),
    "resolved": ("حل شد", False, True),
    "rework": ("بازکاری", True, False),
}
TABLES = {
    "patients": "reference_entities",
    "cases": "cases",
    "tasks": "tasks",
    "followups": "followups",
}
DOCTOR_CONTEXT = {
    "patients": "e.primary_owner_user_id=? OR EXISTS (SELECT 1 FROM cases dc WHERE dc.reference_id=e.id AND dc.workspace_id=e.workspace_id AND dc.unit_id=e.unit_id AND dc.primary_owner_user_id=?)",
    "cases": "e.primary_owner_user_id=? OR e.owner_user_id=?",
    "tasks": "e.assignee_id=? OR EXISTS (SELECT 1 FROM cases dc WHERE dc.id=e.case_id AND dc.workspace_id=e.workspace_id AND dc.primary_owner_user_id=?)",
    "followups": "e.owner_user_id=? OR EXISTS (SELECT 1 FROM cases dc WHERE dc.id=e.case_id AND dc.workspace_id=e.workspace_id AND dc.primary_owner_user_id=?)",
}


def new_id():
    # Short enough for Telegram callback_data while retaining random identity.
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text(value, *, max_length=500, required=True):
    if (
        not isinstance(value, str)
        or len(value.strip()) > max_length
        or (required and not value.strip())
    ):
        raise ValueError("invalid_field")
    return value.strip()


def utc_date(value: str):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("timezone_required") from exc


def audit(scope: Scope, unit_id, action, entity_type, entity_id):
    # Deliberately excludes names, contact info, free text, and clinical data.
    return (
        "INSERT INTO operational_audit(id,workspace_id,unit_id,actor_user_id,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            new_id(),
            scope.workspace_id,
            unit_id,
            str(scope.actor_id),
            action,
            entity_type,
            entity_id,
            now(),
        ),
    )


async def create_organization(
    actor_id: str, bot_key: str, name: str, timezone_name="Asia/Tehran"
):
    ZoneInfo(timezone_name)
    oid, mid = new_id(), new_id()
    await transaction(
        [
            ("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (str(actor_id),)),
            (
                "INSERT INTO workspaces(id,bot_key,name,workspace_type,timezone) VALUES(?,?,?,'healthcare',?)",
                (oid, text(bot_key), text(name), timezone_name),
            ),
            (
                "INSERT INTO workspace_memberships(id,workspace_id,user_id,role) VALUES(?,?,?,'owner')",
                (mid, oid, str(actor_id)),
            ),
            *[
                (
                    "INSERT INTO outcomes(id,workspace_id,key,label,requires_next_action,is_terminal) VALUES(?,?,?,?,?,?)",
                    (new_id(), oid, key, label, int(requires), int(terminal)),
                )
                for key, (label, requires, terminal) in OUTCOMES.items()
            ],
            audit(
                Scope(oid, str(actor_id)),
                None,
                "organization.created",
                "organization",
                oid,
            ),
        ]
    )
    return oid


async def create_branch(scope: Scope, name: str):
    await scope.predicate("branches.manage")
    bid = new_id()
    await transaction(
        [
            (
                "INSERT INTO workspace_units(id,workspace_id,name) VALUES(?,?,?)",
                (bid, scope.workspace_id, text(name)),
            ),
            audit(scope, bid, "branch.created", "branch", bid),
        ]
    )
    return bid


async def set_membership(
    scope: Scope, user_id: str, role: str, unit_id=None, active=True
):
    await scope.predicate("memberships.manage")
    if role not in ROLE_PERMISSIONS or (
        unit_id is None and role not in {"owner", "manager", "admin"}
    ):
        raise ValueError("invalid_role_scope")
    # Tenant administrators cannot grant the owner role or alter an owner.
    is_owner = await fetch_one_sql(
        "SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND role='owner' AND status='active'",
        (scope.workspace_id, str(scope.actor_id)),
    )
    existing = await fetch_one_sql(
        "SELECT * FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND unit_id IS ?",
        (scope.workspace_id, str(user_id), unit_id),
    )
    if not is_owner and (role == "owner" or (existing and existing["role"] == "owner")):
        raise ClinicAccessError("forbidden")
    if existing and existing["role"] == "owner" and (role != "owner" or not active):
        raise ValueError("owner_transfer_required")
    if unit_id:
        await scope.branch(unit_id, "memberships.manage")
    mid = existing["id"] if existing else new_id()
    await transaction(
        [
            ("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (str(user_id),)),
            (
                "INSERT INTO workspace_memberships(id,workspace_id,user_id,unit_id,role,status) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET role=excluded.role,status=excluded.status",
                (
                    mid,
                    scope.workspace_id,
                    str(user_id),
                    unit_id,
                    role,
                    "active" if active else "inactive",
                ),
            ),
            audit(scope, unit_id, "membership.changed", "membership", mid),
        ]
    )
    return mid


async def require_staff(scope: Scope, unit_id: str, user_id: str, *, doctor=False):
    row = await fetch_one_sql(
        "SELECT role FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' AND (unit_id IS NULL OR unit_id=?)"  # nosec B608
        + (" AND role IN ('doctor','dentist')" if doctor else ""),
        (scope.workspace_id, str(user_id), unit_id),
    )  # nosec B608
    if not row:
        raise ValueError("invalid_staff_scope")


async def get_entity(scope: Scope, kind: str, entity_id: str, *, manage=False):
    if kind not in TABLES:
        raise ValueError("invalid_entity")
    predicate, params = await scope.predicate(
        f"{kind}.{'manage' if manage else 'view'}", doctor_context=DOCTOR_CONTEXT[kind]
    )
    row = await fetch_one_sql(
        f"SELECT e.* FROM {TABLES[kind]} e WHERE {predicate} AND e.id=?",  # nosec B608
        params + (entity_id,),
    )  # nosec B608
    if not row:
        raise ClinicAccessError("forbidden")
    return to_healthcare_record(row)


async def list_entities(
    scope: Scope,
    kind: str,
    *,
    unit_id=None,
    owner_id=None,
    doctor_id=None,
    status=None,
    stage=None,
    missing_next_action=False,
    search=None,
    limit=25,
    offset=0,
):
    if kind not in TABLES:
        raise ValueError("invalid_entity")
    pred, args = await scope.predicate(
        f"{kind}.view", doctor_context=DOCTOR_CONTEXT[kind]
    )
    params = list(args)
    if unit_id:
        pred += " AND e.unit_id=?"
        params.append(unit_id)
    if owner_id and kind in {"cases", "followups", "tasks"}:
        pred += (
            " AND e." + ("assignee_id" if kind == "tasks" else "owner_user_id") + "=?"
        )
        params.append(str(owner_id))
    if doctor_id:
        if kind in {"cases", "patients"}:
            pred += " AND e.primary_owner_user_id=?"
        else:
            pred += " AND EXISTS(SELECT 1 FROM cases dc WHERE dc.id=e.case_id AND dc.workspace_id=e.workspace_id AND dc.primary_owner_user_id=?)"
        params.append(str(doctor_id))
    if status:
        pred += " AND e.status=?"
        params.append(status)
    if stage and kind == "cases":
        pred += " AND e.current_stage=?"
        params.append(stage)
    if missing_next_action and kind == "cases":
        pred += " AND e.status='active' AND NOT EXISTS(SELECT 1 FROM tasks na WHERE na.id=e.next_action_task_id AND na.workspace_id=e.workspace_id AND na.case_id=e.id AND na.status IN ('pending','in_progress'))"
    if search and kind == "patients":
        pred += " AND (e.display_name LIKE ? OR e.external_reference=?)"
        params.extend((f"%{text(search)}%", search))
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    total = await fetch_one_sql(
        f"SELECT COUNT(*) AS n FROM {TABLES[kind]} e WHERE {pred}", tuple(params)  # nosec B608
    )  # nosec B608
    rows = await fetch_all_sql(
        f"SELECT e.* FROM {TABLES[kind]} e WHERE {pred} ORDER BY e.created_at,e.id LIMIT ? OFFSET ?",  # nosec B608
        tuple(params) + (limit, offset),
    )  # nosec B608
    return {
        "items": [to_healthcare_record(row) for row in rows],
        "total": total["n"],
        "limit": limit,
        "offset": offset,
    }


async def create_patient(
    scope: Scope,
    unit_id: str,
    display_name: str,
    *,
    external_reference=None,
    phone="",
    doctor_id=None,
):
    await scope.branch(unit_id, "patients.manage")
    if doctor_id:
        await require_staff(scope, unit_id, doctor_id, doctor=True)
    pid, stamp = new_id(), now()
    await transaction(
        [
            (
                "INSERT INTO reference_entities(id,workspace_id,unit_id,reference_type,external_reference,display_name,contact_value,primary_owner_user_id,created_at,updated_at) VALUES(?,?,?,'patient',?,?,?,?,?,?,?)",
                (
                    pid,
                    scope.workspace_id,
                    unit_id,
                    text(external_reference, max_length=100)
                    if external_reference
                    else None,
                    text(display_name, max_length=200),
                    text(phone, max_length=50, required=False),
                    str(doctor_id) if doctor_id else None,
                    stamp,
                    stamp,
                ),
            ),
            audit(scope, unit_id, "patient.created", "patient", pid),
        ]
    )
    return await get_entity(scope, "patients", pid)


async def create_case(
    scope: Scope,
    reference_id: str,
    title: str,
    owner_id: str,
    *,
    case_type="callback",
    doctor_id=None,
    expected_at=None,
    external_reference="",
):
    patient = await get_entity(scope, "patients", reference_id)
    if patient["status"] != "active":
        raise ValueError("patient_is_archived")
    await scope.branch(patient["unit_id"], "cases.manage")
    await require_staff(scope, patient["unit_id"], owner_id)
    doctor_id = doctor_id or patient["primary_owner_user_id"]
    if doctor_id:
        await require_staff(scope, patient["unit_id"], doctor_id, doctor=True)
    # Doctors cannot create a case outside their own patient/doctor relationship.
    actor_roles = await fetch_all_sql(
        "SELECT role FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' AND (unit_id IS NULL OR unit_id=?)",
        (scope.workspace_id, str(scope.actor_id), patient["unit_id"]),
    )
    if all(r["role"] in {"doctor", "dentist"} for r in actor_roles) and str(
        doctor_id
    ) != str(scope.actor_id):
        raise ClinicAccessError("forbidden")
    cid, stamp = new_id(), now()
    await transaction(
        [
            (
                "INSERT INTO cases(id,workspace_id,unit_id,reference_id,title,case_type,owner_user_id,primary_owner_user_id,expected_at,external_reference,opened_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid,
                    scope.workspace_id,
                    patient["unit_id"],
                    reference_id,
                    text(title),
                    text(case_type, max_length=100),
                    str(owner_id),
                    doctor_id,
                    utc_date(expected_at) if expected_at else None,
                    text(external_reference, max_length=200, required=False),
                    stamp,
                    stamp,
                    stamp,
                ),
            ),
            audit(scope, patient["unit_id"], "case.created", "case", cid),
        ]
    )
    return await get_entity(scope, "cases", cid)


def task_insert(scope: Scope, case, task_id, title, owner_id, due_at, workflow_id=None):
    return (
        "INSERT INTO tasks(id,bot_key,user_id,title,status,deadline,created_at,assignee_id,workspace_id,unit_id,reference_id,case_id,workflow_instance_id) VALUES(?,?,?,? ,'pending',?,?,?,?,?,?,?,?)",
        (
            task_id,
            case["bot_key"],
            str(scope.actor_id),
            text(title),
            due_at,
            now(),
            str(owner_id),
            scope.workspace_id,
            case["unit_id"],
            case["reference_id"],
            case["id"],
            workflow_id or case.get("workflow_instance_id"),
        ),
    )


async def case_for_action(scope, case_id):
    case = await get_entity(scope, "cases", case_id)
    await scope.branch(case["unit_id"], "tasks.manage")
    if case["status"] in {"completed", "closed", "cancelled"}:
        raise ValueError("case_is_closed")
    org = await fetch_one_sql(
        "SELECT bot_key FROM workspaces WHERE id=?", (scope.workspace_id,)
    )
    return {**case, "bot_key": org["bot_key"]}


async def create_action(
    scope: Scope,
    case_id: str,
    title: str,
    owner_id: str,
    due_at: str,
    *,
    next_action=True,
):
    case = await case_for_action(scope, case_id)
    await require_staff(scope, case["unit_id"], owner_id)
    tid = new_id()
    statements = [
        task_insert(scope, case, tid, title, owner_id, utc_date(due_at)),
        audit(scope, case["unit_id"], "task.created", "task", tid),
    ]
    if next_action:
        statements.extend(
            [
                (
                    "UPDATE cases SET next_action_task_id=?,updated_at=? WHERE id=? AND workspace_id=?",
                    (tid, now(), case_id, scope.workspace_id),
                ),
                audit(scope, case["unit_id"], "next_action.created", "task", tid),
            ]
        )
    await transaction(statements)
    return await get_entity(scope, "tasks", tid)


async def set_case_status(scope: Scope, case_id: str, status: str, *, blocker=""):
    case = await get_entity(scope, "cases", case_id, manage=True)
    if status not in CASE_STATUSES or (status == "blocked" and not blocker.strip()):
        raise ValueError("invalid_case_status")
    if status == "completed" and await fetch_one_sql(
        "SELECT 1 FROM tasks WHERE workspace_id=? AND case_id=? AND status IN ('pending','in_progress')",
        (scope.workspace_id, case_id),
    ):
        raise ValueError("case_has_pending_actions")
    stamp = now()
    statements = []
    if status in {"closed", "cancelled"}:
        statements.extend(
            [
                (
                    "UPDATE tasks SET status='cancelled' WHERE workspace_id=? AND case_id=? AND status IN ('pending','in_progress')",
                    (scope.workspace_id, case_id),
                ),
                (
                    "UPDATE followups SET status='closed' WHERE workspace_id=? AND case_id=? AND status IN ('due','in_progress')",
                    (scope.workspace_id, case_id),
                ),
            ]
        )
    if status in {"completed", "closed", "cancelled"}:
        statements.append(
            (
                "UPDATE workflow_instances SET status=? WHERE workspace_id=? AND case_id=?",
                (status, scope.workspace_id, case_id),
            )
        )
    await transaction(
        statements
        + [
            (
                "UPDATE cases SET status=?,blocker=?,closed_at=?,updated_at=? WHERE id=? AND workspace_id=?",
                (
                    status,
                    text(blocker, required=False),
                    stamp if status in {"completed", "closed", "cancelled"} else None,
                    stamp,
                    case_id,
                    scope.workspace_id,
                ),
            ),
            audit(scope, case["unit_id"], "case.status_changed", "case", case_id),
        ]
    )
    return await get_entity(scope, "cases", case_id)


async def set_task_status(scope: Scope, task_id: str, status: str):
    task = await get_entity(scope, "tasks", task_id, manage=True)
    if status not in {"pending", "in_progress", "done", "cancelled"}:
        raise ValueError("invalid_status")
    if await fetch_one_sql(
        "SELECT 1 FROM followups WHERE workspace_id=? AND task_id=?",
        (scope.workspace_id, task_id),
    ):
        raise ValueError("followup_outcome_required")
    await transaction(
        [
            (
                "UPDATE tasks SET status=?,completed_at=? WHERE id=? AND workspace_id=?",
                (
                    status,
                    now() if status == "done" else "",
                    task_id,
                    scope.workspace_id,
                ),
            ),
            audit(scope, task["unit_id"], "task.status_changed", "task", task_id),
        ]
    )
    return await get_entity(scope, "tasks", task_id)


async def timeline(scope: Scope, case_id: str):
    case = await get_entity(scope, "cases", case_id)
    # Access to the parent grants timeline access; query still carries full scope.
    tasks = await fetch_all_sql(
        "SELECT t.*,o.key AS outcome_key FROM tasks t LEFT JOIN outcomes o ON o.id=t.outcome_id AND o.workspace_id=t.workspace_id WHERE t.workspace_id=? AND t.unit_id=? AND t.case_id=? ORDER BY t.created_at,t.id",
        (scope.workspace_id, case["unit_id"], case_id),
    )
    return {"case": case, "tasks": tasks}


async def update_patient(
    scope: Scope,
    reference_id: str,
    *,
    display_name=None,
    phone=None,
    doctor_id=None,
    archive=False,
):
    patient = await get_entity(scope, "patients", reference_id, manage=True)
    if doctor_id:
        await require_staff(scope, patient["unit_id"], doctor_id, doctor=True)
    values = {
        "display_name": text(display_name, max_length=200)
        if display_name is not None
        else patient["display_name"],
        "contact_value": text(phone, max_length=50, required=False)
        if phone is not None
        else patient["contact_value"],
        "primary_owner_user_id": str(doctor_id)
        if doctor_id
        else patient["primary_owner_user_id"],
        "status": "archived" if archive else patient["status"],
    }
    await transaction(
        [
            (
                "UPDATE reference_entities SET display_name=?,contact_value=?,primary_owner_user_id=?,status=?,updated_at=? WHERE id=? AND workspace_id=?",
                (*values.values(), now(), reference_id, scope.workspace_id),
            ),
            audit(
                scope,
                patient["unit_id"],
                "patient.archived" if archive else "patient.updated",
                "patient",
                reference_id,
            ),
        ]
    )
    return await get_entity(scope, "patients", reference_id)


async def record_task_outcome(
    scope: Scope, task_id: str, outcome_key: str, *, next_task_id=None
):
    """Record a business result without changing the task's execution status."""
    task = await get_entity(scope, "tasks", task_id, manage=True)
    if await fetch_one_sql(
        "SELECT 1 FROM followups WHERE workspace_id=? AND task_id=?",
        (scope.workspace_id, task_id),
    ):
        raise ValueError("use_followup_outcome")
    outcome = await fetch_one_sql(
        "SELECT * FROM outcomes WHERE workspace_id=? AND key=?",
        (scope.workspace_id, outcome_key),
    )
    if not outcome:
        raise ValueError("invalid_outcome")
    statements = []
    if outcome["requires_next_action"]:
        if not next_task_id or next_task_id == task_id:
            raise ValueError("next_action_required")
        successor = await get_entity(scope, "tasks", next_task_id)
        if (
            not task["case_id"]
            or successor["case_id"] != task["case_id"]
            or successor["status"] not in {"pending", "in_progress"}
        ):
            raise ValueError("invalid_next_action")
        await get_entity(scope, "cases", task["case_id"], manage=True)
        statements.append(
            (
                "UPDATE cases SET next_action_task_id=?,updated_at=? WHERE id=? AND workspace_id=?",
                (next_task_id, now(), task["case_id"], scope.workspace_id),
            )
        )
    statements.extend(
        [
            (
                "UPDATE tasks SET outcome_id=? WHERE id=? AND workspace_id=?",
                (outcome["id"], task_id, scope.workspace_id),
            ),
            audit(scope, task["unit_id"], "task.outcome_changed", "task", task_id),
        ]
    )
    await transaction(statements)
    return await get_entity(scope, "tasks", task_id)
