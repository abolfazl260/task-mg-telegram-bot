"""Deterministic version-pinned workflow definitions; no AI or provider dependency."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.database import fetch_all_sql, fetch_one_sql, get_db, transaction
from services.healthcare.access import Scope
from services.healthcare.service import (
    OUTCOMES,
    audit,
    case_for_action,
    get_entity,
    new_id,
    now,
    require_staff,
    task_insert,
    text,
)


def _definition(stages, role="coordinator"):
    return {
        "trigger": "manual",
        "initial_stage": stages[0],
        "stages": [
            {
                "key": stage,
                "title": stage.replace("_", " "),
                "owner_role": role,
                "due_hours": 24,
                "outcomes": list(OUTCOMES),
                "required_outcome": True,
                "next_action": "required_for_nonterminal_outcome",
                "reminder_policy": "disabled",
                "escalation_policy": "manual",
                "transitions": ([stages[index + 1]] if index + 1 < len(stages) else []),
            }
            for index, stage in enumerate(stages)
        ],
    }


DEFAULT_TEMPLATES = {
    "treatment_plan_followup": _definition(["contact", "decision", "closed"]),
    "general_callback": _definition(["callback", "closed"]),
    "lab_case_tracking": _definition(
        [
            "to_send",
            "sent",
            "in_progress",
            "expected",
            "received",
            "needs_review",
            "ready",
            "completed",
        ],
        "assistant",
    ),
    "post_treatment_followup": _definition(["contact", "review", "closed"]),
    "daily_clinic_checklist": _definition(
        ["opening", "checks", "closing"], "assistant"
    ),
}
# Rework is an explicit branch in the lab workflow, not a free-text status.
DEFAULT_TEMPLATES["lab_case_tracking"]["stages"][5]["transitions"].append("rework")
DEFAULT_TEMPLATES["lab_case_tracking"]["stages"].append(
    {
        **DEFAULT_TEMPLATES["lab_case_tracking"]["stages"][0],
        "key": "rework",
        "title": "rework",
        "transitions": ["sent"],
    }
)


def validate_definition(definition):
    if (
        not isinstance(definition, dict)
        or set(definition) != {"trigger", "initial_stage", "stages"}
        or definition["trigger"] != "manual"
    ):
        raise ValueError("invalid_workflow")
    stages = definition["stages"]
    if not isinstance(stages, list) or not 1 <= len(stages) <= 30:
        raise ValueError("invalid_workflow")
    keys = []
    fields = {
        "key",
        "title",
        "owner_role",
        "due_hours",
        "outcomes",
        "required_outcome",
        "next_action",
        "reminder_policy",
        "escalation_policy",
        "transitions",
    }
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) != fields:
            raise ValueError("invalid_workflow_stage")
        key = text(stage["key"], max_length=50)
        if not all(c.isalnum() or c == "_" for c in key):
            raise ValueError("invalid_stage_key")
        text(stage["title"])
        if stage["owner_role"] not in {
            "coordinator",
            "assistant",
            "reception",
            "doctor",
            "dentist",
            "manager",
        }:
            raise ValueError("invalid_workflow_owner")
        if type(stage["due_hours"]) is not int or not 1 <= stage["due_hours"] <= 8760:
            raise ValueError("invalid_workflow_due")
        if (
            not isinstance(stage["outcomes"], list)
            or not stage["outcomes"]
            or any(o not in OUTCOMES for o in stage["outcomes"])
        ):
            raise ValueError("invalid_workflow_outcomes")
        if (
            stage["required_outcome"] is not True
            or stage["next_action"] != "required_for_nonterminal_outcome"
        ):
            raise ValueError("invalid_outcome_policy")
        # Delivery automation is not implemented yet; reject policies that would
        # promise notifications instead of silently accepting inert settings.
        if (
            stage["reminder_policy"] != "disabled"
            or stage["escalation_policy"] != "manual"
        ):
            raise ValueError("automation_not_available")
        if not isinstance(stage["transitions"], list):
            raise ValueError("invalid_workflow_transition")  # noqa: TRY004 -- API validation contract
        keys.append(key)
    if len(keys) != len(set(keys)) or definition["initial_stage"] not in keys:
        raise ValueError("invalid_workflow_stage")
    for stage in stages:
        if any(target not in keys for target in stage["transitions"]):
            raise ValueError("invalid_workflow_transition")
    return definition


async def publish(scope: Scope, template_key: str, definition: dict):
    await scope.predicate("workflows.manage")
    validate_definition(definition)
    key = text(template_key, max_length=100)
    vid = new_id()
    # One INSERT computes the next version; concurrent database writers serialize.
    await transaction(
        [
            (
                "INSERT INTO workflow_versions(id,workspace_id,template_key,version,definition_json,created_at) SELECT ?,?,?,COALESCE(MAX(version),0)+1,?,? FROM workflow_versions WHERE workspace_id=? AND template_key=?",
                (
                    vid,
                    scope.workspace_id,
                    key,
                    json.dumps(definition, ensure_ascii=False),
                    now(),
                    scope.workspace_id,
                    key,
                ),
            ),
            audit(scope, None, "workflow.published", "workflow_version", vid),
        ]
    )
    return await fetch_one_sql(
        "SELECT * FROM workflow_versions WHERE workspace_id=? AND id=?",
        (scope.workspace_id, vid),
    )


async def seed_defaults(scope: Scope):
    await scope.predicate("workflows.manage")
    for key, definition in DEFAULT_TEMPLATES.items():
        vid = new_id()
        # Seed does not overwrite clinician configuration or publish a new version.
        await transaction(
            [
                (
                    "INSERT INTO workflow_versions(id,workspace_id,template_key,version,definition_json,created_at) SELECT ?,?,?,1,?,? WHERE NOT EXISTS(SELECT 1 FROM workflow_versions WHERE workspace_id=? AND template_key=?)",
                    (
                        vid,
                        scope.workspace_id,
                        key,
                        json.dumps(definition, ensure_ascii=False),
                        now(),
                        scope.workspace_id,
                        key,
                    ),
                ),
            ]
        )
    return await list_templates(scope)


async def list_templates(scope: Scope):
    await scope.predicate("cases.view", doctor_context="?=?")
    return await fetch_all_sql(
        "SELECT v.* FROM workflow_versions v WHERE workspace_id=? AND version=(SELECT MAX(w.version) FROM workflow_versions w WHERE w.workspace_id=v.workspace_id AND w.template_key=v.template_key) ORDER BY template_key",
        (scope.workspace_id,),
    )


async def _owner(scope, branch, owner_id, role):
    await require_staff(scope, branch, owner_id)
    if not await fetch_one_sql(
        "SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' AND (unit_id IS NULL OR unit_id=?) AND role IN (?, 'owner','admin','manager')",
        (scope.workspace_id, str(owner_id), branch, role),
    ):
        raise ValueError("workflow_owner_role_required")


def _action_statements(scope, case, stage, owner_id, workflow_id):
    fid, tid = new_id(), new_id()
    due = (datetime.now(timezone.utc) + timedelta(hours=stage["due_hours"])).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return [
        task_insert(scope, case, tid, stage["title"], owner_id, due, workflow_id),
        (
            "INSERT INTO followups(id,workspace_id,unit_id,reference_id,case_id,task_id,followup_type,owner_user_id,due_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                fid,
                scope.workspace_id,
                case["unit_id"],
                case["reference_id"],
                case["id"],
                tid,
                stage["key"],
                str(owner_id),
                due,
                now(),
            ),
        ),
        (
            "UPDATE cases SET current_stage=?,next_action_task_id=?,updated_at=? WHERE id=? AND workspace_id=?",
            (stage["key"], tid, now(), case["id"], scope.workspace_id),
        ),
        audit(scope, case["unit_id"], "next_action.created", "task", tid),
    ]


async def start(scope: Scope, case_id: str, version_id: str, owner_id: str):
    await get_entity(scope, "cases", case_id, manage=True)
    case = await case_for_action(scope, case_id)
    await scope.branch(case["unit_id"], "followups.manage")
    version = await fetch_one_sql(
        "SELECT * FROM workflow_versions WHERE workspace_id=? AND id=?",
        (scope.workspace_id, version_id),
    )
    if not version or case["workflow_instance_id"]:
        raise ValueError("invalid_workflow_instance")
    definition = json.loads(version["definition_json"])
    stage = next(
        s for s in definition["stages"] if s["key"] == definition["initial_stage"]
    )
    await _owner(scope, case["unit_id"], owner_id, stage["owner_role"])
    wid = new_id()
    await transaction(
        [
            (
                "INSERT INTO workflow_instances(id,workspace_id,unit_id,case_id,version_id,current_stage,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    wid,
                    scope.workspace_id,
                    case["unit_id"],
                    case_id,
                    version_id,
                    stage["key"],
                    now(),
                ),
            ),
            (
                "UPDATE cases SET workflow_instance_id=? WHERE id=? AND workspace_id=?",
                (wid, case_id, scope.workspace_id),
            ),
            *_action_statements(scope, case, stage, owner_id, wid),
            audit(scope, case["unit_id"], "workflow.started", "workflow", wid),
        ]
    )
    return await get_entity(scope, "cases", case_id)


async def transition(
    scope: Scope, case_id: str, target_stage: str, owner_id: str, *, expected_stage: str
):
    await get_entity(scope, "cases", case_id, manage=True)
    case = await case_for_action(scope, case_id)
    await scope.branch(case["unit_id"], "followups.manage")
    db = await get_db()
    async with db.lock:
        await db.conn.execute("BEGIN IMMEDIATE")
        try:
            instance = await fetch_one_sql(
                "SELECT i.*,v.definition_json FROM workflow_instances i JOIN workflow_versions v ON v.id=i.version_id AND v.workspace_id=i.workspace_id WHERE i.workspace_id=? AND i.case_id=?",
                (scope.workspace_id, case_id),
            )
            if not instance or instance["current_stage"] != expected_stage:
                raise ValueError("workflow_stage_conflict")
            definition = json.loads(instance["definition_json"])
            stages = {stage["key"]: stage for stage in definition["stages"]}
            if target_stage not in stages[expected_stage]["transitions"]:
                raise ValueError("invalid_workflow_transition")
            # Outstanding actions must be completed with their own outcome first.
            pending = await fetch_one_sql(
                "SELECT 1 FROM tasks WHERE workspace_id=? AND workflow_instance_id=? AND status IN ('pending','in_progress')",
                (scope.workspace_id, instance["id"]),
            )
            if pending:
                raise ValueError("workflow_action_pending")
            stage = stages[target_stage]
            await _owner(scope, case["unit_id"], owner_id, stage["owner_role"])
            statements = [
                (
                    "UPDATE workflow_instances SET current_stage=? WHERE id=? AND workspace_id=?",
                    (target_stage, instance["id"], scope.workspace_id),
                ),
                *_action_statements(scope, case, stage, owner_id, instance["id"]),
                audit(scope, case["unit_id"], "case.stage_changed", "case", case_id),
            ]
            for sql, params in statements:
                await db.conn.execute(sql, params)
            await db.conn.commit()
        except BaseException:
            await db.conn.rollback()
            raise
    return await get_entity(scope, "cases", case_id)
