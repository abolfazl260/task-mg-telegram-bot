"""Reusable operational-domain service primitives.

This module deliberately has no healthcare terminology. Vertical adapters are
responsible for role names, labels, workflow templates and outcome dictionaries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Mapping
from zoneinfo import ZoneInfo

from services.database import fetch_one_sql, transaction
from services.operations.access import WorkspaceScope


@dataclass(frozen=True)
class OperationsConfig:
    workspace_type: str = "generic"
    reference_type: str = "generic"
    default_timezone: str = "UTC"
    outcomes: Mapping[str, tuple[str, bool, bool]] = field(default_factory=dict)


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text(value, *, max_length=500, required=True) -> str:
    if (
        not isinstance(value, str)
        or len(value.strip()) > max_length
        or (required and not value.strip())
    ):
        raise ValueError("invalid_field")
    return value.strip()


def utc_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("timezone_required") from exc


def audit(scope: WorkspaceScope, unit_id, action, entity_type, entity_id):
    """Return an audit INSERT statement safe to compose into a transaction."""
    return (
        "INSERT INTO operational_audit("
        "id,workspace_id,unit_id,actor_user_id,action,entity_type,entity_id,created_at"
        ") VALUES(?,?,?,?,?,?,?,?)",
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


async def create_workspace(
    actor_id: str,
    bot_key: str,
    name: str,
    *,
    config: OperationsConfig | None = None,
    timezone_name: str | None = None,
    owner_role: str = "owner",
) -> str:
    cfg = config or OperationsConfig()
    zone = timezone_name or cfg.default_timezone
    ZoneInfo(zone)
    workspace_id, membership_id = new_id(), new_id()
    statements = [
        ("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (str(actor_id),)),
        (
            "INSERT INTO workspaces("
            "id,bot_key,name,workspace_type,timezone"
            ") VALUES(?,?,?,?,?)",
            (
                workspace_id,
                text(bot_key),
                text(name),
                text(cfg.workspace_type, max_length=100),
                zone,
            ),
        ),
        (
            "INSERT INTO workspace_memberships("
            "id,workspace_id,user_id,role"
            ") VALUES(?,?,?,?)",
            (membership_id, workspace_id, str(actor_id), text(owner_role, max_length=100)),
        ),
    ]
    statements.extend(
        (
            "INSERT INTO outcomes("
            "id,workspace_id,key,label,requires_next_action,is_terminal"
            ") VALUES(?,?,?,?,?,?)",
            (
                new_id(),
                workspace_id,
                text(key, max_length=100),
                text(label, max_length=200),
                int(requires_next_action),
                int(is_terminal),
            ),
        )
        for key, (label, requires_next_action, is_terminal) in cfg.outcomes.items()
    )
    statements.append(
        (
            "INSERT INTO operational_audit("
            "id,workspace_id,unit_id,actor_user_id,action,entity_type,entity_id,created_at"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (
                new_id(),
                workspace_id,
                None,
                str(actor_id),
                "workspace.created",
                "workspace",
                workspace_id,
                now(),
            ),
        )
    )
    await transaction(statements)
    return workspace_id


async def create_unit(
    scope: WorkspaceScope,
    name: str,
    *,
    permission: str = "units.manage",
    unit_type: str = "branch",
) -> str:
    await scope.predicate(permission, "w", context_predicate="?=?", unit_column="id")
    unit_id = new_id()
    await transaction(
        [
            (
                "INSERT INTO workspace_units("
                "id,workspace_id,name,unit_type"
                ") VALUES(?,?,?,?)",
                (
                    unit_id,
                    scope.workspace_id,
                    text(name),
                    text(unit_type, max_length=100),
                ),
            ),
            audit(scope, unit_id, "unit.created", "unit", unit_id),
        ]
    )
    return unit_id


async def set_membership(
    scope: WorkspaceScope,
    user_id: str,
    role: str,
    *,
    unit_id: str | None = None,
    active: bool = True,
    permission: str = "memberships.manage",
) -> str:
    await scope.predicate(
        permission,
        "w",
        context_predicate="?=?",
        unit_column="id",
    )
    if unit_id:
        await scope.unit(unit_id, permission)
    existing = await fetch_one_sql(
        "SELECT id FROM workspace_memberships "
        "WHERE workspace_id=? AND user_id=? AND unit_id IS ?",
        (scope.workspace_id, str(user_id), unit_id),
    )
    membership_id = existing["id"] if existing else new_id()
    await transaction(
        [
            ("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (str(user_id),)),
            (
                "INSERT INTO workspace_memberships("
                "id,workspace_id,user_id,unit_id,role,status"
                ") VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "role=excluded.role,status=excluded.status",
                (
                    membership_id,
                    scope.workspace_id,
                    str(user_id),
                    unit_id,
                    text(role, max_length=100),
                    "active" if active else "inactive",
                ),
            ),
            audit(scope, unit_id, "membership.changed", "membership", membership_id),
        ]
    )
    return membership_id


async def require_member(
    scope: WorkspaceScope,
    unit_id: str,
    user_id: str,
    *,
    roles: set[str] | frozenset[str] | None = None,
) -> dict:
    sql = (
        "SELECT * FROM workspace_memberships "
        "WHERE workspace_id=? AND user_id=? AND status='active' "
        "AND (unit_id IS NULL OR unit_id=?)"
    )
    params: list[str] = [scope.workspace_id, str(user_id), unit_id]
    if roles:
        placeholders = ",".join("?" for _ in roles)
        sql += f" AND role IN ({placeholders})"  # nosec B608
        params.extend(sorted(roles))
    row = await fetch_one_sql(sql, tuple(params))
    if not row:
        raise scope.ACCESS_ERROR("forbidden")
    return row


async def create_reference(
    scope: WorkspaceScope,
    unit_id: str,
    display_name: str,
    *,
    permission: str = "references.manage",
    reference_type: str = "generic",
    external_reference: str | None = None,
    contact_value: str = "",
    primary_owner_user_id: str | None = None,
) -> dict:
    await scope.unit(unit_id, permission)
    if primary_owner_user_id:
        await require_member(scope, unit_id, primary_owner_user_id)
    reference_id, stamp = new_id(), now()
    await transaction(
        [
            (
                "INSERT INTO reference_entities("
                "id,workspace_id,unit_id,reference_type,external_reference,"
                "display_name,contact_value,primary_owner_user_id,created_at,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    reference_id,
                    scope.workspace_id,
                    unit_id,
                    text(reference_type, max_length=100),
                    text(external_reference, max_length=100)
                    if external_reference
                    else None,
                    text(display_name, max_length=200),
                    text(contact_value, max_length=200, required=False),
                    str(primary_owner_user_id) if primary_owner_user_id else None,
                    stamp,
                    stamp,
                ),
            ),
            audit(scope, unit_id, "reference.created", "reference", reference_id),
        ]
    )
    return await fetch_one_sql(
        "SELECT * FROM reference_entities WHERE workspace_id=? AND id=?",
        (scope.workspace_id, reference_id),
    )


async def create_case(
    scope: WorkspaceScope,
    reference_id: str,
    title: str,
    owner_user_id: str,
    *,
    permission: str = "cases.manage",
    case_type: str = "general",
    primary_owner_user_id: str | None = None,
    expected_at: str | None = None,
    external_reference: str = "",
) -> dict:
    reference = await fetch_one_sql(
        "SELECT * FROM reference_entities "
        "WHERE workspace_id=? AND id=? AND status='active'",
        (scope.workspace_id, reference_id),
    )
    if not reference:
        raise scope.ACCESS_ERROR("forbidden")
    await scope.unit(reference["unit_id"], permission)
    await require_member(scope, reference["unit_id"], owner_user_id)
    if primary_owner_user_id:
        await require_member(scope, reference["unit_id"], primary_owner_user_id)
    case_id, stamp = new_id(), now()
    await transaction(
        [
            (
                "INSERT INTO cases("
                "id,workspace_id,unit_id,reference_id,case_type,title,"
                "owner_user_id,primary_owner_user_id,expected_at,external_reference,"
                "opened_at,created_at,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    case_id,
                    scope.workspace_id,
                    reference["unit_id"],
                    reference_id,
                    text(case_type, max_length=100),
                    text(title),
                    str(owner_user_id),
                    str(primary_owner_user_id) if primary_owner_user_id else None,
                    utc_date(expected_at) if expected_at else None,
                    text(external_reference, max_length=200, required=False),
                    stamp,
                    stamp,
                    stamp,
                ),
            ),
            audit(scope, reference["unit_id"], "case.created", "case", case_id),
        ]
    )
    return await fetch_one_sql(
        "SELECT * FROM cases WHERE workspace_id=? AND id=?",
        (scope.workspace_id, case_id),
    )


async def create_action(
    scope: WorkspaceScope,
    case_id: str,
    title: str,
    owner_user_id: str,
    due_at: str,
    *,
    permission: str = "tasks.manage",
    next_action: bool = True,
) -> dict:
    case = await fetch_one_sql(
        "SELECT c.*,w.bot_key FROM cases c "
        "JOIN workspaces w ON w.id=c.workspace_id "
        "WHERE c.workspace_id=? AND c.id=?",
        (scope.workspace_id, case_id),
    )
    if not case or case["status"] in {"completed", "closed", "cancelled"}:
        raise scope.ACCESS_ERROR("forbidden")
    await scope.unit(case["unit_id"], permission)
    await require_member(scope, case["unit_id"], owner_user_id)
    task_id = new_id()
    statements = [
        (
            "INSERT INTO tasks("
            "id,bot_key,user_id,title,status,deadline,created_at,assignee_id,"
            "workspace_id,unit_id,reference_id,case_id"
            ") VALUES(?,?,?,?,'pending',?,?,?,?,?,?,?)",
            (
                task_id,
                case["bot_key"],
                str(scope.actor_id),
                text(title),
                utc_date(due_at),
                now(),
                str(owner_user_id),
                scope.workspace_id,
                case["unit_id"],
                case["reference_id"],
                case_id,
            ),
        ),
        audit(scope, case["unit_id"], "task.created", "task", task_id),
    ]
    if next_action:
        statements.extend(
            [
                (
                    "UPDATE cases SET next_action_task_id=?,updated_at=? "
                    "WHERE id=? AND workspace_id=?",
                    (task_id, now(), case_id, scope.workspace_id),
                ),
                audit(
                    scope,
                    case["unit_id"],
                    "next_action.created",
                    "task",
                    task_id,
                ),
            ]
        )
    await transaction(statements)
    return await fetch_one_sql(
        "SELECT * FROM tasks WHERE workspace_id=? AND id=?",
        (scope.workspace_id, task_id),
    )
