"""Generic typed attributes for Tasks/Work Items.

Definitions are versioned and values use typed columns for the common scalar
types.  JSON is reserved for structured values such as multi-select fields.
"""
from __future__ import annotations

import json
import hashlib
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

from bot_context import get_current_bot_key
from services.database import execute, fetch_all, fetch_all_sql, fetch_one, fetch_one_sql, transaction
from services.task_service import get_task_by_id_async, user_can_modify_task_async
from services.work_item_type_service import validate_work_item_type_async

DATA_TYPES = {
    "text", "long_text", "number", "boolean", "date", "datetime", "select",
    "multi_select", "phone", "email", "url", "user_reference", "task_reference",
}
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bot() -> str:
    return get_current_bot_key() or "default"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_json(value: str | None, default: Any):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_attribute_json") from exc


def _definition_scope(workspace_id: str | None):
    return str(workspace_id) if workspace_id else None


def _value_hash(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()[:16] if value is not None else ""


def _role_allowed(definition: dict, actor_id, task: dict, action: str, actor_roles=None) -> bool:
    if str(actor_id) == str(task.get("user_id")):
        return True
    roles = _parse_json(definition.get(f"{action}_roles_json"), [])
    return not roles or bool(set(str(r) for r in (actor_roles or [])) & set(str(r) for r in roles))


def _validate_definition_input(field_key: str, data_type: str, validation: dict | None):
    key = str(field_key or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("invalid_attribute_key")
    dtype = str(data_type or "").strip().lower()
    if dtype not in DATA_TYPES:
        raise ValueError("invalid_attribute_type")
    rules = validation if isinstance(validation, dict) else {}
    if "enum" in rules:
        enum = rules["enum"]
        if not isinstance(enum, list) or not enum or any(isinstance(v, (dict, list)) for v in enum):
            raise ValueError("invalid_attribute_enum")
    if "min" in rules or "max" in rules:
        if dtype != "number":
            raise ValueError("invalid_attribute_range")
    return key, dtype, rules


async def create_attribute_definition_async(
    field_key: str, label: str, data_type: str, *, work_item_type: str = "task",
    bot_key: str | None = None, workspace_id: str | None = None, required: bool = False,
    repeatable: bool = False, default: Any = None, validation: dict | None = None,
    searchable: bool = False, filterable: bool = False, sortable: bool = False,
    group_key: str = "", display_order: int = 0, sensitive: bool = False,
    view_roles: list[str] | None = None, edit_roles: list[str] | None = None,
):
    key, dtype, rules = _validate_definition_input(field_key, data_type, validation)
    bot = str(bot_key or _bot())
    item_type = await validate_work_item_type_async(work_item_type, bot)
    if repeatable and dtype in {"boolean", "number", "date", "datetime"}:
        # Repeating scalars are valid; keeping this explicit documents the API.
        pass
    candidate = await validate_attribute_value_async(
        default, dtype, rules, allow_none=not required
    ) if default is not None else None
    previous = await fetch_one_sql(
        """SELECT MAX(version) AS version FROM task_attribute_definitions
           WHERE bot_key=? AND workspace_id IS ? AND work_item_type=? AND field_key=?""",
        (bot, _definition_scope(workspace_id), item_type, key),
    )
    version = int((previous or {}).get("version") or 0) + 1
    definition_id = str(uuid.uuid4())
    now = _now()
    await transaction([
        ("""UPDATE task_attribute_definitions SET active=0, updated_at=?
           WHERE bot_key=? AND workspace_id IS ? AND work_item_type=? AND field_key=? AND active=1""",
         (now, bot, _definition_scope(workspace_id), item_type, key)),
        ("""INSERT INTO task_attribute_definitions
           (id,bot_key,workspace_id,work_item_type,field_key,label,data_type,required,repeatable,
            default_value_json,validation_json,searchable,filterable,sortable,group_key,display_order,
            active,version,created_at,updated_at,sensitive,view_roles_json,edit_roles_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
         (definition_id, bot, _definition_scope(workspace_id), item_type, key, str(label or key), dtype,
          int(bool(required)), int(bool(repeatable)), _json(candidate) if candidate is not None else None,
          _json(rules), int(bool(searchable)), int(bool(filterable)), int(bool(sortable)), str(group_key or ""),
          int(display_order), 1, version, now, now, int(bool(sensitive)), _json(view_roles or []), _json(edit_roles or []))),
    ])
    return await get_attribute_definition_async(definition_id)


async def get_attribute_definition_async(definition_id: str):
    return await fetch_one("task_attribute_definitions", "id=?", (str(definition_id),))


async def list_attribute_definitions_async(*, work_item_type: str = "task", bot_key: str | None = None,
                                           workspace_id: str | None = None, include_inactive: bool = False):
    bot = str(bot_key or _bot())
    item_type = await validate_work_item_type_async(work_item_type, bot)
    active_clause = "" if include_inactive else " AND active=1"
    rows = await fetch_all_sql(
        f"""SELECT * FROM task_attribute_definitions
            WHERE bot_key=? AND workspace_id IS ? AND work_item_type=?{active_clause}
            ORDER BY display_order ASC, field_key ASC, version DESC""",
        (bot, _definition_scope(workspace_id), item_type),
    )
    for row in rows:
        row["default"] = _parse_json(row.pop("default_value_json", None), None)
        row["validation"] = _parse_json(row.pop("validation_json", "{}"), {})
    return rows


def _validate_iso_date(value: Any, *, datetime_value: bool = False) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")) if datetime_value else date.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_attribute_value") from exc
    return parsed.isoformat()


async def validate_attribute_value_async(value: Any, data_type: str, validation: dict | None = None, *, allow_none: bool = False):
    dtype = str(data_type or "").lower()
    rules = validation if isinstance(validation, dict) else {}
    if value is None:
        if allow_none:
            return None
        raise ValueError("required_attribute")
    if dtype in {"text", "long_text", "phone", "email", "url"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("invalid_attribute_value")
        result = value.strip()
        if dtype == "email" and ("@" not in result or result.startswith("@") or result.endswith("@")):
            raise ValueError("invalid_attribute_value")
        if dtype == "url" and not re.match(r"^https?://", result, re.I):
            raise ValueError("invalid_attribute_value")
    elif dtype == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("invalid_attribute_value")
        result = float(value) if isinstance(value, float) else int(value)
    elif dtype == "boolean":
        if not isinstance(value, bool):
            raise ValueError("invalid_attribute_value")
        result = value
    elif dtype == "date":
        result = _validate_iso_date(value)
    elif dtype == "datetime":
        result = _validate_iso_date(value, datetime_value=True)
    elif dtype == "select":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("invalid_attribute_value")
        result = value.strip()
    elif dtype == "multi_select":
        if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v.strip() for v in value):
            raise ValueError("invalid_attribute_value")
        result = list(dict.fromkeys(v.strip() for v in value))
    elif dtype in {"user_reference", "task_reference"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("invalid_attribute_value")
        result = value.strip()
    else:
        raise ValueError("invalid_attribute_type")
    enum = rules.get("enum")
    if enum and ((dtype == "multi_select" and any(v not in enum for v in result)) or (dtype != "multi_select" and result not in enum)):
        raise ValueError("invalid_attribute_enum_value")
    if dtype == "number":
        if "min" in rules and result < rules["min"]:
            raise ValueError("attribute_below_minimum")
        if "max" in rules and result > rules["max"]:
            raise ValueError("attribute_above_maximum")
    if "regex" in rules and isinstance(result, str) and not re.fullmatch(str(rules["regex"]), result):
        raise ValueError("invalid_attribute_value")
    return result


def _typed_columns(dtype: str, value: Any) -> dict[str, Any]:
    columns = {"value_text": None, "value_number": None, "value_boolean": None,
               "value_date": None, "value_datetime": None, "value_json": None}
    if dtype in {"text", "long_text", "phone", "email", "url", "select", "user_reference", "task_reference"}:
        columns["value_text"] = value
    elif dtype == "number":
        columns["value_number"] = value
    elif dtype == "boolean":
        columns["value_boolean"] = int(value)
    elif dtype == "date":
        columns["value_date"] = value
    elif dtype == "datetime":
        columns["value_datetime"] = value
    else:
        columns["value_json"] = _json(value)
    return columns


async def _resolve_definition_async(task: dict, field_key: str, definition_id: str | None = None):
    if definition_id:
        definition = await get_attribute_definition_async(definition_id)
    else:
        rows = await fetch_all_sql(
            """SELECT * FROM task_attribute_definitions WHERE bot_key=? AND workspace_id IS ?
               AND work_item_type=? AND field_key=? AND active=1 ORDER BY version DESC LIMIT 1""",
            (task.get("bot_key") or "default", task.get("workspace_id"), task.get("work_item_type") or "task", field_key),
        )
        definition = rows[0] if rows else None
    if not definition or definition.get("active") != 1:
        raise ValueError("attribute_definition_not_found")
    return definition


async def set_task_attribute_async(task_id, field_key, value, actor_id, *, definition_id: str | None = None, ordinal: int = 0, actor_roles=None):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        raise PermissionError("attribute_permission_denied")
    definition = await _resolve_definition_async(task, field_key, definition_id)
    if not _role_allowed(definition, actor_id, task, "edit", actor_roles):
        raise PermissionError("attribute_field_edit_denied")
    if not definition.get("repeatable") and int(ordinal) != 0:
        raise ValueError("attribute_not_repeatable")
    normalized = await validate_attribute_value_async(
        value, definition["data_type"], _parse_json(definition.get("validation_json"), {}),
        allow_none=not bool(definition.get("required")),
    )
    cols = _typed_columns(definition["data_type"], normalized)
    now = _now()
    value_id = str(uuid.uuid4())
    previous = await fetch_one_sql("SELECT * FROM task_attribute_values WHERE task_id=? AND definition_id=? AND ordinal=?", (str(task_id), definition["id"], int(ordinal)))
    await execute(
        """INSERT INTO task_attribute_values
           (id,task_id,definition_id,definition_version,ordinal,value_text,value_number,value_boolean,value_date,value_datetime,value_json,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(task_id,definition_id,ordinal) DO UPDATE SET
             definition_version=excluded.definition_version,value_text=excluded.value_text,value_number=excluded.value_number,
             value_boolean=excluded.value_boolean,value_date=excluded.value_date,value_datetime=excluded.value_datetime,
             value_json=excluded.value_json,updated_at=excluded.updated_at""",
        (value_id, str(task_id), definition["id"], definition["version"], int(ordinal), cols["value_text"], cols["value_number"],
         cols["value_boolean"], cols["value_date"], cols["value_datetime"], cols["value_json"], now, now),
    )
    await execute("INSERT INTO task_attribute_audit(id,task_id,definition_id,actor_id,action,old_value_hash,new_value_hash,created_at) VALUES(?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), str(task_id), definition["id"], str(actor_id), "write", _value_hash(previous), _value_hash(normalized), now))
    return await get_task_attributes_async(task_id, actor_id)


async def get_task_attributes_async(task_id, actor_id, *, actor_roles=None):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        raise PermissionError("attribute_permission_denied")
    rows = await fetch_all_sql(
        """SELECT d.*,v.ordinal,v.value_text,v.value_number,v.value_boolean,v.value_date,v.value_datetime,v.value_json,v.definition_version
           FROM task_attribute_values v JOIN task_attribute_definitions d ON d.id=v.definition_id
           WHERE v.task_id=? ORDER BY d.display_order,d.field_key,v.ordinal""",
        (str(task_id),),
    )
    result = []
    for row in rows:
        if not _role_allowed(row, actor_id, task, "view", actor_roles):
            continue
        dtype = row["data_type"]
        if dtype in {"text", "long_text", "phone", "email", "url", "select", "user_reference", "task_reference"}:
            value = row["value_text"]
        elif dtype == "number":
            value = row["value_number"]
        elif dtype == "boolean":
            value = bool(row["value_boolean"]) if row["value_boolean"] is not None else None
        elif dtype == "date":
            value = row["value_date"]
        elif dtype == "datetime":
            value = row["value_datetime"]
        else:
            value = _parse_json(row["value_json"], None)
        row["value"] = value
        row.pop("value_text", None); row.pop("value_number", None); row.pop("value_boolean", None)
        row.pop("value_date", None); row.pop("value_datetime", None); row.pop("value_json", None)
        row["validation"] = _parse_json(row.pop("validation_json", "{}"), {})
        row["default"] = _parse_json(row.pop("default_value_json", None), None)
        row["sensitive"] = bool(row.get("sensitive"))
        result.append(row)
    return result


async def validate_required_attributes_async(task_id, actor_id):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        raise PermissionError("attribute_permission_denied")
    definitions = await list_attribute_definitions_async(
        work_item_type=task.get("work_item_type") or "task", bot_key=task.get("bot_key") or "default",
        workspace_id=task.get("workspace_id"),
    )
    values = {item["field_key"] for item in await get_task_attributes_async(task_id, actor_id) if item.get("value") is not None}
    return [item["field_key"] for item in definitions if item.get("required") and item["field_key"] not in values and item.get("default") is None]


def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)


create_attribute_definition = lambda *a, **k: _run(create_attribute_definition_async(*a, **k))
list_attribute_definitions = lambda *a, **k: _run(list_attribute_definitions_async(*a, **k))
set_task_attribute = lambda *a, **k: _run(set_task_attribute_async(*a, **k))
get_task_attributes = lambda *a, **k: _run(get_task_attributes_async(*a, **k))
validate_required_attributes = lambda *a, **k: _run(validate_required_attributes_async(*a, **k))
