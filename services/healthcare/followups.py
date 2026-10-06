"""Patient follow-up queue; outcomes and next actions commit atomically."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from services.database import fetch_all_sql, fetch_one_sql, get_db, transaction
from services.healthcare.access import Scope
from services.healthcare.service import (
    DOCTOR_CONTEXT,
    audit,
    case_for_action,
    get_entity,
    new_id,
    now,
    require_staff,
    task_insert,
    text,
    utc_date,
)


async def create_followup(
    scope: Scope,
    case_id: str,
    owner_id: str,
    due_at: str,
    *,
    title="پیگیری بیمار",
    followup_type="callback",
):
    case = await case_for_action(scope, case_id)
    await scope.branch(case["branch_id"], "followups.manage")
    await require_staff(scope, case["branch_id"], owner_id)
    fid, tid, due = new_id(), new_id(), utc_date(due_at)
    await transaction(
        [
            task_insert(scope, case, tid, title, owner_id, due),
            (
                "INSERT INTO clinic_followups(id,organization_id,branch_id,patient_id,case_id,task_id,followup_type,owner_user_id,due_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    fid,
                    scope.organization_id,
                    case["branch_id"],
                    case["patient_id"],
                    case_id,
                    tid,
                    text(followup_type, max_length=100),
                    str(owner_id),
                    due,
                    now(),
                ),
            ),
            (
                "UPDATE clinic_cases SET next_action_task_id=?,updated_at=? WHERE id=? AND organization_id=?",
                (tid, now(), case_id, scope.organization_id),
            ),
            audit(scope, case["branch_id"], "followup.created", "followup", fid),
            audit(scope, case["branch_id"], "next_action.created", "task", tid),
        ]
    )
    return await get_entity(scope, "followups", fid)


async def record_outcome(
    scope: Scope,
    followup_id: str,
    outcome_key: str,
    *,
    next_due_at=None,
    next_owner_id=None,
):
    followup = await get_entity(scope, "followups", followup_id, manage=True)
    case = await case_for_action(scope, followup["case_id"])
    await get_entity(scope, "tasks", followup["task_id"], manage=True)
    outcome = await fetch_one_sql(
        "SELECT * FROM clinic_outcomes WHERE organization_id=? AND key=?",
        (scope.organization_id, outcome_key),
    )
    if case.get("workflow_instance_id"):
        workflow = await fetch_one_sql(
            "SELECT i.current_stage,v.definition_json FROM clinic_workflow_instances i JOIN clinic_workflow_versions v ON v.id=i.version_id AND v.organization_id=i.organization_id WHERE i.organization_id=? AND i.id=?",
            (scope.organization_id, case["workflow_instance_id"]),
        )
        stage = next(
            s
            for s in json.loads(workflow["definition_json"])["stages"]
            if s["key"] == workflow["current_stage"]
        )
        if outcome_key not in stage["outcomes"]:
            raise ValueError("outcome_not_allowed")
    if not outcome:
        raise ValueError("invalid_outcome")
    if outcome["requires_next_action"] and not next_due_at:
        raise ValueError("next_action_required")
    if next_due_at and not outcome["requires_next_action"]:
        raise ValueError("terminal_outcome_has_no_next_action")
    due = utc_date(next_due_at) if next_due_at else None
    owner_id = str(next_owner_id or followup["owner_user_id"])
    if due:
        await require_staff(scope, case["branch_id"], owner_id)
    db = await get_db()
    async with db.lock:
        await db.conn.execute("BEGIN IMMEDIATE")
        try:
            # Read again under the write lock: retries/overlap must never create
            # another successor or replace an already recorded result.
            async with db.conn.execute(
                "SELECT * FROM clinic_followups WHERE id=? AND organization_id=?",
                (followup_id, scope.organization_id),
            ) as cur:
                current = dict(await cur.fetchone())
            if current["outcome_id"]:
                if current["outcome_id"] != outcome["id"]:
                    raise ValueError("outcome_already_recorded")
                await db.conn.rollback()
                return current
            fid, tid = (new_id(), new_id()) if due else (None, None)
            stamp = now()
            statements = [
                (
                    "UPDATE tasks SET outcome_id=?,status='done',completed_at=? WHERE id=? AND organization_id=?",
                    (outcome["id"], stamp, current["task_id"], scope.organization_id),
                ),
            ]
            if due:
                statements.extend(
                    [
                        task_insert(scope, case, tid, "پیگیری بعدی", owner_id, due),
                        (
                            "INSERT INTO clinic_followups(id,organization_id,branch_id,patient_id,case_id,task_id,followup_type,owner_user_id,due_at,attempt_number,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                fid,
                                scope.organization_id,
                                case["branch_id"],
                                case["patient_id"],
                                case["id"],
                                tid,
                                current["followup_type"],
                                owner_id,
                                due,
                                current["attempt_number"] + 1,
                                stamp,
                            ),
                        ),
                        (
                            "UPDATE clinic_cases SET next_action_task_id=?,updated_at=? WHERE id=? AND organization_id=?",
                            (tid, stamp, case["id"], scope.organization_id),
                        ),
                        audit(
                            scope, case["branch_id"], "next_action.created", "task", tid
                        ),
                    ]
                )
            statements.extend(
                [
                    (
                        "UPDATE clinic_followups SET status=?,outcome_id=?,next_followup_id=?,completed_at=? WHERE id=? AND organization_id=?",
                        (
                            "rescheduled" if due else "completed",
                            outcome["id"],
                            fid,
                            stamp,
                            followup_id,
                            scope.organization_id,
                        ),
                    ),
                    audit(
                        scope,
                        case["branch_id"],
                        f"followup.{outcome_key}",
                        "followup",
                        followup_id,
                    ),
                ]
            )
            for sql, params in statements:
                await db.conn.execute(sql, params)
            await db.conn.commit()
        except BaseException:
            await db.conn.rollback()
            raise
    return await get_entity(scope, "followups", followup_id)


async def queue(
    scope: Scope,
    view="today",
    *,
    branch_id=None,
    owner_id=None,
    doctor_id=None,
    limit=25,
    offset=0,
    at=None,
):
    pred, args = await scope.predicate(
        "followups.view", doctor_context=DOCTOR_CONTEXT["followups"]
    )
    params = list(args)
    org = await fetch_one_sql(
        "SELECT timezone FROM clinic_organizations WHERE id=?", (scope.organization_id,)
    )
    zone = ZoneInfo(org["timezone"])
    current = (at or datetime.now(timezone.utc)).astimezone(zone)
    start = datetime.combine(current.date(), time.min, zone)
    end = datetime.combine(current.date() + timedelta(days=1), time.min, zone)
    start_utc, end_utc = utc_date(start.isoformat()), utc_date(end.isoformat())
    if view in {"today", "overdue", "upcoming"}:
        pred += " AND e.status IN ('due','in_progress')"
        if view == "today":
            pred += " AND e.due_at>=? AND e.due_at<?"
            params.extend((start_utc, end_utc))
        elif view == "overdue":
            pred += " AND e.due_at<?"
            params.append(utc_date(current.isoformat()))
        else:
            pred += " AND e.due_at>=?"
            params.append(end_utc)
    elif view == "no_answer":
        pred += " AND o.key='no_answer'"
    elif view == "rescheduled":
        pred += " AND e.status='rescheduled'"
    else:
        raise ValueError("invalid_queue_view")
    for column, value in (("branch_id", branch_id), ("owner_user_id", owner_id)):
        if value:
            pred += f" AND e.{column}=?"
            params.append(str(value))
    if doctor_id:
        pred += " AND c.primary_doctor_user_id=?"
        params.append(str(doctor_id))
    joins = "FROM clinic_followups e JOIN clinic_cases c ON c.id=e.case_id AND c.organization_id=e.organization_id AND c.branch_id=e.branch_id LEFT JOIN clinic_outcomes o ON o.id=e.outcome_id AND o.organization_id=e.organization_id"
    total = await fetch_one_sql(
        f"SELECT COUNT(*) AS n {joins} WHERE {pred}", tuple(params)
    )
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    rows = await fetch_all_sql(
        f"SELECT e.*,o.key AS outcome_key,c.primary_doctor_user_id {joins} WHERE {pred} ORDER BY e.due_at,e.id LIMIT ? OFFSET ?",
        tuple(params) + (limit, offset),
    )
    return {"items": rows, "total": total["n"], "limit": limit, "offset": offset}
