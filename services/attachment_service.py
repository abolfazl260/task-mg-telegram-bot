"""Permission-aware attachments for typed Work Items.

The service stores only file metadata and an opaque backend/file identifier.  A
Telegram file id or storage key is returned only after the parent Work Item has
passed authorization; no public URL is generated here.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from bot_context import get_current_bot_key
from services.database import execute, fetch_all_sql, fetch_one_sql

_SENSITIVE_KEYS = {"url", "public_url", "download_url", "token", "secret", "password", "access_token"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bot() -> str:
    return get_current_bot_key() or "default"


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return {str(k): v for k, v in metadata.items() if str(k).lower() not in _SENSITIVE_KEYS}


async def _parent(task_id: str) -> dict | None:
    return await fetch_one_sql("SELECT * FROM tasks WHERE id=?", (str(task_id),))


async def _authorized(task: dict | None, actor_id: str, *, write: bool = False) -> bool:
    from services.work_item_access import authorized_task
    if not task:
        return False
    try:
        await authorized_task(task['id'], actor_id, write=write)
        return True
    except PermissionError:
        return False


async def _validate_attribute(task: dict, definition_id: str | None, ordinal: int, actor_id, *, write=False) -> None:
    if not definition_id:
        return
    if int(ordinal) < 0:
        raise ValueError("invalid_attribute_ordinal")
    definition = await fetch_one_sql(
        """SELECT * FROM task_attribute_definitions
           WHERE id=? AND bot_key=? AND workspace_id IS ? AND work_item_type=?""",
        (str(definition_id), task.get("bot_key") or "default", task.get("workspace_id"), task.get("work_item_type") or "task"),
    )
    if not definition:
        raise ValueError("attribute_definition_not_found")
    from services.work_item_access import field_allowed
    if not await field_allowed(definition, task, actor_id, action='edit' if write else 'view'):
        raise PermissionError('attachment_field_permission_denied')
    if ordinal and not definition.get('repeatable'):
        raise ValueError('attribute_not_repeatable')


async def attach_file_async(
    task_id: str,
    actor_id: str,
    *,
    file_id: str,
    filename: str = "",
    media_type: str = "application/octet-stream",
    size_bytes: int = 0,
    storage_key: str = "",
    attribute_definition_id: str | None = None,
    attribute_ordinal: int = 0,
    metadata: dict[str, Any] | None = None,
) -> dict:
    """Attach an opaque file reference to a Work Item or one of its attributes."""
    if not str(file_id or "").strip():
        raise ValueError("file_id_required")
    try:
        size = int(size_bytes)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_file_size") from exc
    if size < 0:
        raise ValueError("invalid_file_size")
    task = await _parent(task_id)
    if not await _authorized(task, actor_id, write=True):
        raise PermissionError("attachment_permission_denied")
    await _validate_attribute(task, attribute_definition_id, attribute_ordinal, actor_id, write=True)
    attachment_id = str(uuid.uuid4())
    await execute(
        """INSERT INTO task_attachments(
           id,bot_key,workspace_id,task_id,attribute_definition_id,attribute_ordinal,
           file_id,storage_key,filename,media_type,size_bytes,created_by,created_at,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            attachment_id, task.get("bot_key") or _bot(), task.get("workspace_id"), str(task_id),
            str(attribute_definition_id) if attribute_definition_id else None, int(attribute_ordinal),
            str(file_id), str(storage_key or ""), str(filename or "")[:255],
            str(media_type or "application/octet-stream")[:160], size, str(actor_id), _now(),
            json.dumps(_safe_metadata(metadata), ensure_ascii=False),
        ),
    )
    return await get_attachment_async(attachment_id, actor_id)


async def get_attachment_async(attachment_id: str, actor_id: str, *, include_archived: bool = False) -> dict | None:
    row = await fetch_one_sql("SELECT * FROM task_attachments WHERE id=?", (str(attachment_id),))
    if not row:
        return None
    if row.get("archived_at") and not include_archived:
        return None
    task = await _parent(row["task_id"])
    if not await _authorized(task, actor_id):
        raise PermissionError("attachment_permission_denied")
    await _validate_attribute(task, row.get("attribute_definition_id"), row.get("attribute_ordinal", 0), actor_id)
    try:
        metadata = json.loads(row.get("metadata_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    row.pop("metadata_json", None)
    row["metadata"] = _safe_metadata(metadata)
    # Explicitly avoid manufacturing a URL. The opaque identifiers are usable
    # only by the authorized Telegram/Web adapter that owns the storage backend.
    row.pop("public_url", None)
    return row


async def list_attachments_async(task_id: str, actor_id: str, *, attribute_definition_id: str | None = None, include_archived: bool = False, limit: int = 100, offset: int = 0) -> list[dict]:
    task = await _parent(task_id)
    if not await _authorized(task, actor_id):
        raise PermissionError("attachment_permission_denied")
    limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
    clauses = ["task_id=?"]
    params: list[Any] = [str(task_id)]
    if not include_archived:
        clauses.append("archived_at IS NULL")
    if attribute_definition_id:
        clauses.append("attribute_definition_id=?")
        params.append(str(attribute_definition_id))
    rows = await fetch_all_sql(
        "SELECT * FROM task_attachments WHERE " + " AND ".join(clauses) + " ORDER BY created_at,id LIMIT ? OFFSET ?",
        tuple(params) + (limit, offset),
    )
    result = []
    for row in rows:
        try:
            result.append(await get_attachment_async(row["id"], actor_id, include_archived=include_archived))
        except PermissionError:
            continue
    return [item for item in result if item]


async def archive_attachment_async(attachment_id: str, actor_id: str) -> bool:
    row = await fetch_one_sql("SELECT * FROM task_attachments WHERE id=?", (str(attachment_id),))
    if not row:
        return False
    task = await _parent(row["task_id"])
    if not await _authorized(task, actor_id, write=True):
        raise PermissionError("attachment_permission_denied")
    await _validate_attribute(task, row.get("attribute_definition_id"), row.get("attribute_ordinal", 0), actor_id, write=True)
    await execute("UPDATE task_attachments SET archived_at=? WHERE id=? AND archived_at IS NULL", (_now(), str(attachment_id)))
    return True


async def unarchive_attachment_async(attachment_id: str, actor_id: str) -> bool:
    row = await fetch_one_sql("SELECT * FROM task_attachments WHERE id=?", (str(attachment_id),))
    if not row:
        return False
    task = await _parent(row["task_id"])
    if not await _authorized(task, actor_id, write=True):
        raise PermissionError("attachment_permission_denied")
    await _validate_attribute(task, row.get("attribute_definition_id"), row.get("attribute_ordinal", 0), actor_id, write=True)
    await execute("UPDATE task_attachments SET archived_at=NULL WHERE id=?", (str(attachment_id),))
    return True


def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)

attach_file = lambda *a, **k: _run(attach_file_async(*a, **k))
get_attachment = lambda *a, **k: _run(get_attachment_async(*a, **k))
list_attachments = lambda *a, **k: _run(list_attachments_async(*a, **k))
archive_attachment = lambda *a, **k: _run(archive_attachment_async(*a, **k))
unarchive_attachment = lambda *a, **k: _run(unarchive_attachment_async(*a, **k))
