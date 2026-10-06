"""Generic, permission-aware Report Definition Engine.

Definitions are data, while execution builds only from an allow-listed source and
field registry.  Vertical profiles can add labels and definitions without
embedding Clinic-specific query code in the core service.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from bot_context import get_current_bot_key
from services.database import execute, fetch_all_sql, fetch_one_sql

METRICS = {"count", "sum", "avg", "min", "max", "rate"}
SOURCE_FIELDS = {
    "task": {"id", "work_item_type", "status", "priority", "unit_id", "assignee_id", "user_id", "created_at", "deadline", "category"},
    "session": {"id", "work_item_type", "status", "unit_id", "assignee_id", "user_id", "created_at", "deadline", "category"},
    "followup": {"id", "status", "unit_id", "owner_user_id", "created_at", "due_at", "attempt_number"},
    "patient": {"id", "reference_type", "unit_id", "primary_owner_user_id", "status", "created_at", "updated_at", "display_name"},
    "case": {"id", "case_type", "unit_id", "owner_user_id", "primary_owner_user_id", "status", "opened_at", "created_at", "expected_at"},
}
SOURCE_TABLES = {
    "task": ("tasks", "s"), "session": ("tasks", "s"), "followup": ("followups", "s"),
    "patient": ("reference_entities", "s"), "case": ("cases", "s"),
}
NUMERIC_FIELDS = {"attempt_number"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bot() -> str:
    return get_current_bot_key() or "default"


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def _parse(value: Any, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_report_definition_json") from exc


def _source(source_item_type: str):
    source = str(source_item_type or "").strip().lower()
    if source not in SOURCE_TABLES:
        raise ValueError("invalid_report_source")
    table, alias = SOURCE_TABLES[source]
    fields = set(SOURCE_FIELDS[source])
    if source == "session":
        fields.add("work_item_type")
    return source, table, alias, fields


def _validate_filters(filters: dict | None, fields: set[str]) -> dict:
    if filters is None:
        return {}
    if not isinstance(filters, dict):
        raise ValueError("invalid_report_filters")
    for key, condition in filters.items():
        if key not in fields:
            raise ValueError("invalid_report_filter_field")
        if isinstance(condition, dict):
            if set(condition) - {"eq", "in", "contains", "gte", "lte", "neq"}:
                raise ValueError("invalid_report_filter_operator")
            if "in" in condition and (not isinstance(condition["in"], list) or len(condition["in"]) > 100):
                raise ValueError("invalid_report_filter_values")
        elif isinstance(condition, list):
            if len(condition) > 100:
                raise ValueError("invalid_report_filter_values")
        elif not isinstance(condition, (str, int, float, bool)) and condition is not None:
            raise ValueError("invalid_report_filter_value")
    return filters


async def create_report_definition_async(
    *, name: str, title: str, source_item_type: str, created_by: str,
    workspace_id: str | None = None, bot_key: str | None = None,
    filters: dict | None = None, group_by: str = "", date_field: str = "created_at",
    metric: str = "count", label: str = "", role_permissions: list[str] | None = None,
    branch_scope: str = "any", drill_down: dict | None = None,
) -> dict:
    source, _table, _alias, fields = _source(source_item_type)
    if not str(name or "").strip() or len(str(name)) > 120:
        raise ValueError("invalid_report_name")
    if not str(title or "").strip():
        raise ValueError("invalid_report_title")
    metric = str(metric or "count").lower()
    if metric not in METRICS:
        raise ValueError("invalid_report_metric")
    group_by = str(group_by or "").strip()
    if group_by and group_by not in fields:
        raise ValueError("invalid_report_group_by")
    date_field = str(date_field or "created_at").strip()
    if date_field not in fields:
        raise ValueError("invalid_report_date_field")
    if metric in {"sum", "avg", "min", "max"}:
        value_field = (drill_down or {}).get("value_field") if isinstance(drill_down, dict) else None
        if value_field not in fields or value_field not in NUMERIC_FIELDS:
            raise ValueError("invalid_report_metric_field")
    filters = _validate_filters(filters, fields)
    bot = str(bot_key or _bot())
    now = _now()
    report_id = str(uuid.uuid4())
    previous = await fetch_one_sql(
        "SELECT MAX(version) AS version FROM report_definitions WHERE bot_key=? AND workspace_id IS ? AND name=?",
        (bot, workspace_id, str(name).strip()),
    )
    version = int((previous or {}).get("version") or 0) + 1
    await execute(
        """INSERT INTO report_definitions(
           id,bot_key,workspace_id,name,title,source_item_type,filters_json,group_by,date_field,
           metric,label,role_permissions_json,branch_scope,drill_down_json,version,created_by,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (report_id, bot, workspace_id, str(name).strip(), str(title).strip(), source, _json(filters), group_by,
         date_field, metric, str(label or title).strip(), _json(role_permissions or []), str(branch_scope or "any"),
         _json(drill_down or {}), version, str(created_by), now, now),
    )
    return await get_report_definition_async(report_id, str(created_by))


async def get_report_definition_async(report_id: str, actor_id: str | None = None, *, include_inactive: bool = False) -> dict | None:
    row = await fetch_one_sql("SELECT * FROM report_definitions WHERE id=?", (str(report_id),))
    if not row or (not include_inactive and not row.get("active")):
        return None
    if actor_id is not None and not await _can_access_definition(row, actor_id):
        raise PermissionError("report_permission_denied")
    row["filters"] = _parse(row.pop("filters_json", "{}"), {})
    row["role_permissions"] = _parse(row.pop("role_permissions_json", "[]"), [])
    row["drill_down"] = _parse(row.pop("drill_down_json", "{}"), {})
    return row


async def _can_access_definition(definition: dict, actor_id: str) -> bool:
    workspace_id = definition.get("workspace_id")
    if not workspace_id:
        return str(definition.get("created_by")) == str(actor_id)
    row = await fetch_one_sql(
        "SELECT role FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' LIMIT 1",
        (workspace_id, str(actor_id)),
    )
    if not row:
        return False
    allowed = _parse(definition.get("role_permissions_json"), [])
    return not allowed or row.get("role") in allowed


async def list_report_definitions_async(*, actor_id: str, workspace_id: str | None = None, bot_key: str | None = None, source_item_type: str | None = None) -> list[dict]:
    clauses = ["active=1", "bot_key=?"]
    params: list[Any] = [str(bot_key or _bot())]
    if workspace_id:
        clauses.append("workspace_id=?")
        params.append(str(workspace_id))
    else:
        clauses.append("workspace_id IS NULL")
    if source_item_type:
        _source(source_item_type)
        clauses.append("source_item_type=?")
        params.append(str(source_item_type).lower())
    rows = await fetch_all_sql("SELECT * FROM report_definitions WHERE " + " AND ".join(clauses) + " ORDER BY title,id", tuple(params))
    result = []
    for row in rows:
        if await _can_access_definition(row, actor_id):
            result.append(await get_report_definition_async(row["id"], actor_id))
    return result


def _condition_sql(column: str, condition: Any, params: list[Any]) -> str:
    if isinstance(condition, dict):
        pieces = []
        for op, value in condition.items():
            if op == "in":
                if not value:
                    pieces.append("1=0")
                else:
                    pieces.append(f"{column} IN ({','.join('?' for _ in value)})")
                    params.extend(value)
            elif op == "contains": pieces.append(f"{column} LIKE ?"); params.append(f"%{value}%")
            elif op == "eq": pieces.append(f"{column}=?"); params.append(value)
            elif op == "neq": pieces.append(f"{column}!=?"); params.append(value)
            elif op == "gte": pieces.append(f"{column}>=?"); params.append(value)
            elif op == "lte": pieces.append(f"{column}<=?"); params.append(value)
        return " AND ".join(pieces) or "1=1"
    if isinstance(condition, list):
        if not condition: return "1=0"
        params.extend(condition)
        return f"{column} IN ({','.join('?' for _ in condition)})"
    params.append(condition)
    return f"{column}=?"


async def execute_report_async(report_id: str, actor_id: str, *, from_date: str | None = None, to_date: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    definition = await get_report_definition_async(report_id, actor_id)
    if not definition:
        raise ValueError("report_not_found")
    source, table, alias, fields = _source(definition["source_item_type"])
    clauses: list[str] = []
    params: list[Any] = []
    if definition.get("workspace_id"):
        membership = await fetch_one_sql(
            "SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' LIMIT 1",
            (definition["workspace_id"], str(actor_id)),
        )
        if not membership:
            raise PermissionError("report_permission_denied")
        clauses.append(f"{alias}.workspace_id=?"); params.append(definition["workspace_id"])
        if source in {"task", "session"}:
            clauses.append(f"{alias}.work_item_type=?" if source == "session" else "1=1")
            if source == "session": params.append("session")
        elif source == "patient": clauses.append(f"{alias}.reference_type='patient'")
    else:
        clauses.extend([f"{alias}.bot_key=?", f"{alias}.user_id=?"] if source in {"task", "session"} else ["1=0"])
        params.extend((definition.get("bot_key") or _bot(), str(actor_id)) if source in {"task", "session"} else ())
    if definition.get("branch_scope") not in (None, "", "any"):
        if "unit_id" not in fields: raise ValueError("invalid_report_branch_scope")
        clauses.append(f"{alias}.unit_id=?"); params.append(definition["branch_scope"])
    for field, condition in definition.get("filters", {}).items():
        clauses.append(_condition_sql(f"{alias}.{field}", condition, params))
    if from_date:
        clauses.append(f"{alias}.{definition['date_field']}>=?"); params.append(str(from_date))
    if to_date:
        clauses.append(f"{alias}.{definition['date_field']}<=?"); params.append(str(to_date))
    where = " AND ".join(clauses) or "1=1"
    group = definition.get("group_by")
    metric = definition.get("metric") or "count"
    value_field = (definition.get("drill_down") or {}).get("value_field")
    if group:
        metric_expr = "COUNT(*)" if metric in {"count", "rate"} else f"{metric.upper()}({alias}.{value_field})"
        sql = f"SELECT {alias}.{group} AS group_value,{metric_expr} AS value FROM {table} {alias} WHERE {where} GROUP BY {alias}.{group} ORDER BY value DESC,group_value"
    else:
        if metric == "count": metric_expr = "COUNT(*)"
        elif metric == "rate": metric_expr = "COUNT(*)"
        else: metric_expr = f"{metric.upper()}({alias}.{value_field})"
        sql = f"SELECT {metric_expr} AS value FROM {table} {alias} WHERE {where}"
    aggregate_rows = await fetch_all_sql(sql, tuple(params))
    total = sum(float(r.get("value") or 0) for r in aggregate_rows) if group else float((aggregate_rows[0] if aggregate_rows else {}).get("value") or 0)
    if metric == "rate":
        denominator = await fetch_one_sql(f"SELECT COUNT(*) AS n FROM {table} {alias} WHERE {where}", tuple(params))
        total = (float(total) / float(denominator.get("n") or 1)) if denominator else 0.0
    page, page_size = max(1, int(page)), max(1, min(int(page_size), 200))
    offset = (page - 1) * page_size
    drill_sql = f"SELECT {alias}.* FROM {table} {alias} WHERE {where} ORDER BY {alias}.{definition['date_field']} DESC, {alias}.id DESC LIMIT ? OFFSET ?"
    drill_rows = await fetch_all_sql(drill_sql, tuple(params) + (page_size, offset))
    return {"definition": definition, "summary": {"value": total, "metric": metric, "empty": not bool(drill_rows)}, "groups": aggregate_rows if group else [], "rows": drill_rows, "page": page, "page_size": page_size}


def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)

create_report_definition = lambda *a, **k: _run(create_report_definition_async(*a, **k))
get_report_definition = lambda *a, **k: _run(get_report_definition_async(*a, **k))
list_report_definitions = lambda *a, **k: _run(list_report_definitions_async(*a, **k))
execute_report = lambda *a, **k: _run(execute_report_async(*a, **k))
