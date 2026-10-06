"""Permission-aware generic contact points attached to Work Items."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from services.database import execute, fetch_all_sql, fetch_one, fetch_one_sql, transaction
from services.task_service import get_task_by_id_async, user_can_modify_task_async

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
CONTACT_TYPES = {"phone", "email", "address", "other"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_contact_value(contact_type: str, value: str) -> str:
    text = str(value or "").translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS).strip()
    if contact_type == "phone":
        text = re.sub(r"[^0-9+]", "", text)
        if text.startswith("00"):
            text = "+" + text[2:]
        # Keep Iranian local and international forms searchable as one value.
        if text.startswith("+98") and len(text) == 13:
            text = "0" + text[3:]
        elif text.startswith("98") and len(text) == 12:
            text = "0" + text[2:]
        return text
    if contact_type == "email":
        return text.casefold()
    return re.sub(r"\s+", " ", text).casefold()


async def create_contact_point_async(task_id, contact_type, value, actor_id, *, label="", is_primary=False, note="", status="active"):
    ctype = str(contact_type or "").strip().lower()
    if ctype not in CONTACT_TYPES or not str(value or "").strip():
        raise ValueError("invalid_contact_point")
    if status not in {"active", "inactive"}:
        raise ValueError("invalid_contact_status")
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        raise PermissionError("contact_point_permission_denied")
    normalized = normalize_contact_value(ctype, value)
    if not normalized:
        raise ValueError("invalid_contact_point")
    duplicate = await fetch_one_sql(
        "SELECT id FROM task_contact_points WHERE task_id=? AND type=? AND normalized_value=? AND status='active' LIMIT 1",
        (str(task_id), ctype, normalized),
    )
    if duplicate:
        raise ValueError("duplicate_contact_point")
    point_id, now = str(uuid.uuid4()), _now()
    statements = []
    if is_primary and status == "active":
        statements.append(("UPDATE task_contact_points SET is_primary=0,updated_at=? WHERE task_id=? AND type=? AND status='active'", (now, str(task_id), ctype)))
    statements.append(("""INSERT INTO task_contact_points
        (id,workspace_id,task_id,type,label,value,normalized_value,is_primary,note,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (point_id, task.get("workspace_id"), str(task_id), ctype, str(label or ""), str(value).strip(), normalized, int(bool(is_primary)), str(note or ""), status, now, now)))
    await transaction(statements)
    return await get_contact_point_async(point_id, actor_id)


async def get_contact_point_async(point_id, actor_id):
    row = await fetch_one("task_contact_points", "id=?", (str(point_id),))
    if not row:
        return None
    task = await get_task_by_id_async(row["task_id"])
    if not task or not await user_can_modify_task_async(actor_id, task):
        raise PermissionError("contact_point_permission_denied")
    return row


async def list_contact_points_async(task_id, actor_id, *, contact_type=None, include_inactive=False):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        raise PermissionError("contact_point_permission_denied")
    clauses = ["task_id=?"]
    params = [str(task_id)]
    if contact_type:
        ctype = str(contact_type).lower()
        if ctype not in CONTACT_TYPES:
            raise ValueError("invalid_contact_type")
        clauses.append("type=?"); params.append(ctype)
    if not include_inactive:
        clauses.append("status='active'")
    return await fetch_all_sql("SELECT * FROM task_contact_points WHERE " + " AND ".join(clauses) + " ORDER BY type,is_primary DESC,created_at,id", tuple(params))


async def update_contact_point_async(point_id, actor_id, *, value=None, label=None, is_primary=None, note=None, status=None):
    point = await get_contact_point_async(point_id, actor_id)
    if not point:
        return False
    task_id, ctype = point["task_id"], point["type"]
    updates, params = [], []
    normalized = point["normalized_value"]
    if value is not None:
        if not str(value).strip(): raise ValueError("invalid_contact_point")
        normalized = normalize_contact_value(ctype, value)
        duplicate = await fetch_one_sql("SELECT id FROM task_contact_points WHERE task_id=? AND type=? AND normalized_value=? AND id!=? AND status='active'", (task_id, ctype, normalized, point_id))
        if duplicate: raise ValueError("duplicate_contact_point")
        updates += ["value=?", "normalized_value=?"]; params += [str(value).strip(), normalized]
    if label is not None: updates.append("label=?"); params.append(str(label))
    if note is not None: updates.append("note=?"); params.append(str(note))
    if status is not None:
        if status not in {"active", "inactive"}: raise ValueError("invalid_contact_status")
        updates.append("status=?"); params.append(status)
    now = _now()
    if is_primary is True:
        await execute("UPDATE task_contact_points SET is_primary=0,updated_at=? WHERE task_id=? AND type=? AND status='active'", (now, task_id, ctype))
        updates.append("is_primary=1")
    elif is_primary is False:
        updates.append("is_primary=0")
    if not updates: return point
    updates.append("updated_at=?"); params += [now, point_id]
    await execute("UPDATE task_contact_points SET " + ",".join(updates) + " WHERE id=?", tuple(params))
    return await get_contact_point_async(point_id, actor_id)


async def search_contact_points_async(query, actor_id, *, workspace_id=None, contact_type=None):
    normalized = normalize_contact_value(contact_type or "other", query)
    if not normalized: return []
    clauses = ["cp.normalized_value LIKE ?", "cp.status='active'", "t.workspace_id IS ?"]
    params = [f"%{normalized}%", workspace_id]
    if contact_type:
        clauses.append("cp.type=?"); params.append(contact_type)
    rows = await fetch_all_sql("SELECT cp.*,t.title,t.user_id,t.workspace_id FROM task_contact_points cp JOIN tasks t ON t.id=cp.task_id WHERE " + " AND ".join(clauses) + " ORDER BY cp.created_at DESC", tuple(params))
    allowed = []
    for row in rows:
        task = await get_task_by_id_async(row["task_id"])
        if task and await user_can_modify_task_async(actor_id, task): allowed.append(row)
    return allowed


def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)

normalize_contact = normalize_contact_value
create_contact_point = lambda *a, **k: _run(create_contact_point_async(*a, **k))
list_contact_points = lambda *a, **k: _run(list_contact_points_async(*a, **k))
update_contact_point = lambda *a, **k: _run(update_contact_point_async(*a, **k))
search_contact_points = lambda *a, **k: _run(search_contact_points_async(*a, **k))
