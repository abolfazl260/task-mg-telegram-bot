"""Versioned, vertical-neutral form/detail/list layout schemas."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from bot_context import get_current_bot_key
from services.database import fetch_all_sql, fetch_one, transaction
from services.work_item_type_service import validate_work_item_type_async

KINDS = {"create", "edit", "detail", "list"}


def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _bot(): return get_current_bot_key() or "default"


def validate_view_schema(schema: dict, kind: str) -> dict:
    if kind not in KINDS or not isinstance(schema, dict):
        raise ValueError("invalid_view_schema")
    result = json.loads(json.dumps(schema, ensure_ascii=False))
    if kind == "list":
        columns = result.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ValueError("invalid_view_schema_columns")
        keys = set()
        for column in columns:
            if not isinstance(column, dict) or not str(column.get("field_key") or "").strip():
                raise ValueError("invalid_view_schema_field")
            key = str(column["field_key"])
            if key in keys: raise ValueError("duplicate_view_schema_field")
            keys.add(key)
            column.setdefault("visible", True); column.setdefault("order", len(keys) - 1)
    else:
        sections = result.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError("invalid_view_schema_sections")
        section_keys = set(); field_keys = set()
        for section in sections:
            if not isinstance(section, dict) or not str(section.get("key") or "").strip():
                raise ValueError("invalid_view_schema_section")
            if section["key"] in section_keys: raise ValueError("duplicate_view_schema_section")
            section_keys.add(section["key"])
            section.setdefault("label", section["key"]); section.setdefault("collapsed", False)
            fields = section.get("fields", [])
            if not isinstance(fields, list): raise ValueError("invalid_view_schema_fields")
            for field in fields:
                if not isinstance(field, dict) or not str(field.get("field_key") or "").strip():
                    raise ValueError("invalid_view_schema_field")
                key = str(field["field_key"])
                if key in field_keys: raise ValueError("duplicate_view_schema_field")
                field_keys.add(key)
                field.setdefault("visible", True); field.setdefault("editable", kind != "detail")
                field.setdefault("order", len(field_keys) - 1)
    result.setdefault("responsive", {})
    result.setdefault("terminology", {})
    return result


async def save_view_schema_async(schema, *, work_item_type="task", schema_kind="detail", bot_key=None, workspace_id=None):
    bot = str(bot_key or _bot())
    item_type = await validate_work_item_type_async(work_item_type, bot)
    normalized = validate_view_schema(schema, schema_kind)
    previous = await fetch_all_sql("SELECT MAX(version) AS version FROM task_view_schemas WHERE bot_key=? AND workspace_id IS ? AND work_item_type=? AND schema_kind=?", (bot, workspace_id, item_type, schema_kind))
    version = int((previous[0] or {}).get("version") or 0) + 1
    now, schema_id = _now(), str(uuid.uuid4())
    await transaction([
        ("UPDATE task_view_schemas SET active=0,updated_at=? WHERE bot_key=? AND workspace_id IS ? AND work_item_type=? AND schema_kind=? AND active=1", (now, bot, workspace_id, item_type, schema_kind)),
        ("INSERT INTO task_view_schemas(id,bot_key,workspace_id,work_item_type,schema_kind,schema_json,version,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (schema_id,bot,workspace_id,item_type,schema_kind,json.dumps(normalized,ensure_ascii=False),version,1,now,now)),
    ])
    return await get_view_schema_async(work_item_type=item_type, schema_kind=schema_kind, bot_key=bot, workspace_id=workspace_id)


async def get_view_schema_async(*, work_item_type="task", schema_kind="detail", bot_key=None, workspace_id=None, version=None):
    bot = str(bot_key or _bot()); item_type = await validate_work_item_type_async(work_item_type, bot)
    clause = "version=?" if version is not None else "active=1"
    params = (bot, workspace_id, item_type, schema_kind) + ((int(version),) if version is not None else ())
    row = await fetch_one("task_view_schemas", f"bot_key=? AND workspace_id IS ? AND work_item_type=? AND schema_kind=? AND {clause}", params)
    if not row: return None
    row["schema"] = json.loads(row.pop("schema_json")); return row


save_view_schema = lambda *a, **k: __import__("services.database", fromlist=["_run"])._run(save_view_schema_async(*a, **k))
get_view_schema = lambda *a, **k: __import__("services.database", fromlist=["_run"])._run(get_view_schema_async(*a, **k))
