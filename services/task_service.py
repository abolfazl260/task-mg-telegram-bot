from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from bot_context import get_current_bot_key
from services.database import _run as db_run
from services.database import (
    execute,
    fetch_all,
    fetch_all_sql,
    fetch_one,
    fetch_one_sql,
    get_db,
    transaction,
)
from services.team_service import acan_edit, aget_team, ais_member
from services.work_item_type_service import (
    get_work_item_type_profile_async,
    validate_work_item_type_async,
)

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "in_progress", "done", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high"}
MAX_HIERARCHY_DEPTH = 10

def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
def _bot(): return get_current_bot_key() or "default"
def _new_task_id(): return str(uuid.uuid4())

async def _ensure_user_async(uid):
    uid=str(uid or "")
    if uid: await execute("INSERT OR IGNORE INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)",(uid,"UTC","jalali"))


async def _hierarchy_parent_async(task_id: str | None):
    if not task_id:
        return None
    return await fetch_one("tasks", "id=?", (str(task_id),))


async def _validate_parent_async(parent_task_id: str | None, child_type: str, actor_id: str,
                                 *, child_task_id: str | None = None):
    """Validate scope, authorization, type compatibility and bounded depth."""
    if not parent_task_id:
        return None
    parent = await _hierarchy_parent_async(parent_task_id)
    if not parent:
        raise ValueError("parent_task_not_found")
    if child_task_id and str(parent_task_id) == str(child_task_id):
        raise ValueError("hierarchy_cycle")
    if not await user_can_modify_task_async(actor_id, parent):
        raise PermissionError("parent_task_permission_denied")
    if not await _can_be_child_async(parent, child_type):
        raise ValueError("invalid_child_type")

    profile = await get_work_item_type_profile_async(_bot())
    child_definition = profile["types"].get(child_type)
    if child_definition is None:
        raise ValueError("invalid_work_item_type")
    allowed_parents = child_definition.get("allowed_parent_types") or []
    if allowed_parents and parent.get("work_item_type") not in allowed_parents:
        raise ValueError("invalid_parent_type")

    # Walk ancestors in the service layer so moves cannot introduce cycles and
    # the maximum depth remains bounded even on older SQLite installations.
    depth = 1
    cursor = parent
    seen = {str(child_task_id)} if child_task_id else set()
    while cursor and cursor.get("parent_task_id"):
        current_id = str(cursor["parent_task_id"])
        if current_id in seen:
            raise ValueError("hierarchy_cycle")
        seen.add(current_id)
        depth += 1
        if depth >= MAX_HIERARCHY_DEPTH:
            raise ValueError("hierarchy_depth_exceeded")
        cursor = await _hierarchy_parent_async(current_id)
    return parent


async def _can_be_child_async(parent: dict[str, Any], child_type: str) -> bool:
    profile = await get_work_item_type_profile_async(_bot())
    definition = profile["types"].get(parent.get("work_item_type"))
    if definition is None:
        return False
    allowed = definition.get("allowed_child_types") or []
    return not allowed or child_type in allowed

# Tasks are shared user data. bot_key is retained only as provenance/configuration metadata;
# it must never be used to isolate a user's tasks between bots.
async def read_tasks_async(): return await fetch_all("tasks", "workspace_id IS NULL")

async def get_task_dashboard_counts_async(user_id: int) -> dict[str, int]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db = await get_db()
    query = """SELECT SUM(CASE WHEN status IN ('pending', 'in_progress') THEN 1 ELSE 0 END), SUM(CASE WHEN substr(COALESCE(deadline, ''), 1, 10) = ? AND status NOT IN ('done', 'cancelled') THEN 1 ELSE 0 END), SUM(CASE WHEN substr(COALESCE(deadline, ''), 1, 10) < ? AND status NOT IN ('done', 'cancelled') THEN 1 ELSE 0 END) FROM tasks WHERE workspace_id IS NULL AND user_id = ?"""
    async with db.conn.execute(query, (today, today, str(user_id))) as cursor: row = await cursor.fetchone()
    return {"count_active": int((row[0] if row else 0) or 0), "count_today": int((row[1] if row else 0) or 0), "count_overdue": int((row[2] if row else 0) or 0)}

async def save_task_async(data):
    v=list(data)+[""]*20; task_id=str(v[0] or _new_task_id()); user_id=str(v[1] or "")
    if not user_id: raise ValueError("task user_id is required")
    await _ensure_user_async(user_id)
    if v[12]: await _ensure_user_async(v[12])
    item_type = await validate_work_item_type_async(None, _bot())
    await execute("""INSERT INTO tasks(id,bot_key,work_item_type,user_id,title,priority,status,deadline,category,tags,description,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(task_id,_bot(),item_type,user_id,v[2] or "",v[3] or "medium",v[4] or "pending",v[5] or "",v[6] or "",v[7] or "",v[8] or "",v[9] or "",v[10] or "",v[11] or None,v[12] or None,v[13] or "",v[14] or ""))
    return task_id

async def update_task_status_async(task_id,new_status,actor_id):
    if new_status not in VALID_STATUSES: return False
    task=await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id,task): return False
    await execute("UPDATE tasks SET status=?,completed_at=? WHERE id=?",(new_status,_now() if new_status=="done" else "",task_id)); return True

async def create_task_async(user_id,title,priority,deadline,category,tags,description="",team_id="",assignee=None,work_item_type=None,parent_task_id=None,creation_request_id=None):
    if priority not in VALID_PRIORITIES: raise ValueError("invalid priority")
    item_type = await validate_work_item_type_async(work_item_type, _bot())
    await _ensure_user_async(user_id)
    # A create draft can carry one stable UUID across retries. Reuse it as the
    # task PK so SQLite enforces idempotency across workers and bot restarts.
    tid = str(uuid.UUID(str(creation_request_id))) if creation_request_id else _new_task_id()
    if creation_request_id:
        existing = await fetch_one("tasks", "id=?", (tid,))
        if existing:
            if str(existing.get("user_id")) != str(user_id) or existing.get("bot_key") != _bot():
                raise ValueError("creation_request_conflict")
            return tid
    await _validate_parent_async(parent_task_id, item_type, str(user_id))
    if team_id and not category:
        team=await aget_team(team_id); category=team.get("name","") if team else category
    aid=str((assignee or {}).get("user_id") or "") or None
    if aid: await _ensure_user_async(aid)
    now=_now(); statements=[("""INSERT INTO tasks(id,bot_key,work_item_type,parent_task_id,user_id,title,priority,status,deadline,category,tags,description,created_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(tid,_bot(),item_type,parent_task_id or None,str(user_id),title,priority,"pending",deadline or "",category or "",tags or "",description or "",now,team_id or None,aid,(assignee or {}).get("display_name") or "",(assignee or {}).get("username") or ""))]
    if assignee: statements.append(("""INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)""",(tid,str(user_id),"assigned","",(assignee or {}).get("display_name") or "",now)))
    try:
        await transaction(statements)
    except sqlite3.IntegrityError:
        if not creation_request_id:
            raise
        # A competing callback may have committed the same request first.
        existing = await fetch_one("tasks", "id=?", (tid,))
        if not existing or str(existing.get("user_id")) != str(user_id) or existing.get("bot_key") != _bot():
            raise
    return tid


async def create_child_task_async(parent_task_id, user_id, title, priority="medium", deadline="",
                                  category="", tags="", description="", team_id="",
                                  assignee=None, work_item_type=None):
    """Create a typed child while keeping the regular task API available."""
    return await create_task_async(
        user_id, title, priority, deadline, category, tags, description,
        team_id, assignee, work_item_type, parent_task_id,
    )


async def get_parent_task_async(task_id):
    task = await get_task_by_id_async(task_id)
    if not task or not task.get("parent_task_id"):
        return None
    return await get_task_by_id_async(task["parent_task_id"])


async def list_child_tasks_async(parent_task_id, actor_id, *, limit=50, offset=0,
                                 include_archived=True):
    parent = await get_task_by_id_async(parent_task_id)
    if not parent or not await user_can_modify_task_async(actor_id, parent):
        return []
    try:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        raise ValueError("invalid_pagination")
    archived_clause = "" if include_archived else " AND archived_at IS NULL"
    return await fetch_all_sql(
        f"SELECT * FROM tasks WHERE parent_task_id=?{archived_clause} ORDER BY created_at ASC, rowid ASC LIMIT ? OFFSET ?",
        (str(parent_task_id), limit, offset),
    )


async def count_child_tasks_async(parent_task_id, actor_id, *, include_archived=True):
    parent = await get_task_by_id_async(parent_task_id)
    if not parent or not await user_can_modify_task_async(actor_id, parent):
        return {"total": 0, "active": 0, "done": 0, "archived": 0}
    archived_clause = "" if include_archived else " AND archived_at IS NULL"
    row = await fetch_one_sql(
        f"""SELECT COUNT(*) AS total,
            SUM(CASE WHEN status NOT IN ('done','cancelled') AND archived_at IS NULL THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
            SUM(CASE WHEN archived_at IS NOT NULL THEN 1 ELSE 0 END) AS archived
            FROM tasks WHERE parent_task_id=?{archived_clause}""",
        (str(parent_task_id),),
    )
    return {key: int(row.get(key) or 0) for key in ("total", "active", "done", "archived")}


async def move_child_task_async(task_id, parent_task_id, actor_id):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        return False
    if parent_task_id is not None:
        parent = await _validate_parent_async(parent_task_id, task.get("work_item_type") or "task", str(actor_id), child_task_id=task_id)
        if parent and (parent.get("workspace_id") != task.get("workspace_id") or (parent.get("workspace_id") is None and str(parent.get("user_id")) != str(task.get("user_id")))):
            raise ValueError("parent_task_scope_mismatch")
    await execute("UPDATE tasks SET parent_task_id=? WHERE id=?", (parent_task_id, task_id))
    return True


async def archive_task_async(task_id, actor_id):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        return False
    await execute("UPDATE tasks SET archived_at=? WHERE id=?", (_now(), task_id))
    return True


async def unarchive_task_async(task_id, actor_id):
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(actor_id, task):
        return False
    await execute("UPDATE tasks SET archived_at=NULL WHERE id=?", (task_id,))
    return True

async def update_task_async(task_id,user_id,**changes):
    task=await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(user_id,task): return False
    allowed={"title","description","priority","deadline","category","tags"}
    values={k:v for k,v in changes.items() if k in allowed and v is not None}
    if "priority" in values and values["priority"] not in VALID_PRIORITIES: raise ValueError("invalid priority")
    if not values: return True
    assignments=", ".join(f"{key}=?" for key in values)
    await execute(f"UPDATE tasks SET {assignments} WHERE id=?",tuple(values.values())+(task_id,))
    return True


# Bounded task queries for interactive consumers. Legacy full-list functions
# below remain available for workflows that explicitly process all tasks.
DEFAULT_TASK_PAGE_SIZE = 50
MAX_TASK_PAGE_SIZE = 100


def _task_pagination(limit: int, offset: int) -> tuple[int, int]:
    try:
        limit, offset = int(limit), int(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_pagination") from exc
    if limit < 1 or offset < 0:
        raise ValueError("invalid_pagination")
    return min(limit, MAX_TASK_PAGE_SIZE), offset


async def list_visible_tasks_page_async(
    user_id, team_id=None, *, active=False, work_item_type=None,
    limit=DEFAULT_TASK_PAGE_SIZE, offset=0, sort_key="created",
) -> dict:
    """SQL-scoped pagination across personal and current team memberships.

    Bot keys are provenance, not a visibility boundary. Workspace records are
    deliberately excluded. EXISTS avoids duplicate rows for team memberships.
    """
    limit, offset = _task_pagination(limit, offset)
    item_type = await validate_work_item_type_async(work_item_type, _bot()) if work_item_type else None
    if team_id:
        if not await ais_member(team_id, user_id):
            return {"tasks": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}
        conditions = ["t.workspace_id IS NULL", "t.team_id=?"]
        params = [str(team_id)]
    else:
        conditions = [
            "t.workspace_id IS NULL",
            """(((t.team_id IS NULL OR t.team_id='') AND t.user_id=?)
                OR ((t.team_id IS NOT NULL AND t.team_id!='') AND EXISTS (
                    SELECT 1 FROM team_members tm
                    WHERE tm.team_id=t.team_id AND tm.user_id=?
                )))""",
        ]
        params = [str(user_id), str(user_id)]
    if active:
        conditions.append("t.status IN ('pending','in_progress')")
    if item_type:
        conditions.append("t.work_item_type=?")
        params.append(item_type)
    where = " AND ".join(conditions)
    # Column names and sort expressions are fixed: never interpolate caller SQL.
    orderings = {
        "created": "t.created_at DESC,t.id DESC",
        "deadline": "CASE WHEN COALESCE(t.deadline,'')='' THEN 1 ELSE 0 END,t.deadline ASC,t.id ASC",
        "priority": "CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 9 END,t.created_at DESC,t.id DESC",
    }
    if sort_key not in orderings:
        raise ValueError("invalid_task_sort")
    count = await fetch_one_sql("SELECT COUNT(*) AS n FROM tasks t WHERE " + where, tuple(params))
    total = int((count or {}).get("n") or 0)
    tasks = await fetch_all_sql(
        "SELECT t.* FROM tasks t WHERE " + where
        + " ORDER BY " + orderings[sort_key] + " LIMIT ? OFFSET ?",
        tuple(params) + (limit, offset),
    )
    return {
        "tasks": tasks, "total": total, "limit": limit, "offset": offset,
        "has_more": offset + len(tasks) < total,
    }


async def get_visible_task_by_id_async(user_id, task_id) -> dict | None:
    """Check one task's read scope in SQL, never by loading the user's archive."""
    return await fetch_one_sql(
        """SELECT t.* FROM tasks t
           WHERE t.id=? AND t.workspace_id IS NULL
             AND (((t.team_id IS NULL OR t.team_id='') AND t.user_id=?)
               OR ((t.team_id IS NOT NULL AND t.team_id!='') AND EXISTS (
                   SELECT 1 FROM team_members tm
                   WHERE tm.team_id=t.team_id AND tm.user_id=?
               )))""",
        (str(task_id), str(user_id), str(user_id)),
    )


async def _visible_async(user_id,team_id=None,active=False,work_item_type=None):
    item_type = await validate_work_item_type_async(work_item_type, _bot()) if work_item_type else None
    if team_id:
        if not await ais_member(team_id,user_id): return []
        where="workspace_id IS NULL AND team_id=?"+((" AND status IN ('pending','in_progress')") if active else "")
        params=[team_id]
        if item_type:
            where += " AND work_item_type=?"
            params.append(item_type)
        return await fetch_all("tasks",where,tuple(params))

    uid = str(user_id)
    active_only = 1 if active else 0
    return await fetch_all_sql(
        """SELECT t.*
            FROM tasks AS t
            WHERE t.workspace_id IS NULL AND (t.team_id IS NULL OR t.team_id='')
              AND t.user_id=?
              AND (?=0 OR t.status IN ('pending','in_progress'))
              AND (? IS NULL OR t.work_item_type=?)
            UNION ALL
            SELECT t.*
            FROM tasks AS t
            JOIN team_members AS tm ON tm.team_id=t.team_id
            WHERE t.workspace_id IS NULL AND tm.user_id=?
              AND (?=0 OR t.status IN ('pending','in_progress'))
              AND (? IS NULL OR t.work_item_type=?)""",
        (uid, active_only, item_type, item_type, uid, active_only, item_type, item_type),
    )

async def get_active_tasks_async(user_id,team_id=None,work_item_type=None): return await _visible_async(user_id,team_id,True,work_item_type)
async def get_all_user_tasks_async(user_id,team_id=None,work_item_type=None): return await _visible_async(user_id,team_id,False,work_item_type)
async def get_team_tasks_async(team_id,user_id,active_only=True,work_item_type=None):
    if not await ais_member(team_id,user_id): return []
    item_type = await validate_work_item_type_async(work_item_type, _bot()) if work_item_type else None
    where="workspace_id IS NULL AND team_id=?"+(" AND status IN ('pending','in_progress')" if active_only else "")
    params=[team_id]
    if item_type:
        where += " AND work_item_type=?"
        params.append(item_type)
    return await fetch_all("tasks",where,tuple(params))
async def get_task_by_id_async(task_id): return await fetch_one("tasks","workspace_id IS NULL AND id=?",(task_id,))
async def user_can_modify_task_async(user_id,task): return bool(task and not task.get("workspace_id") and (await acan_edit(task.get("team_id"),user_id) if task.get("team_id") else str(task.get("user_id"))==str(user_id)))
async def change_task_status_async(task_id,new_status,actor_id): return await update_task_status_async(task_id,new_status,actor_id)
async def search_tasks_async(user_id,query):
    q=(query or "").strip().lower()
    if not q: return []
    return [t for t in await get_all_user_tasks_async(user_id) if q in " ".join(str(t.get(k) or "") for k in ("title","category","tags","description")).lower()]
async def get_all_user_ids_async(): return sorted({str(t.get("user_id")) for t in await read_tasks_async() if t.get("user_id")})
async def assign_task_async(task_id,assignee,actor_id,action="assigned"):
    t=await get_task_by_id_async(task_id)
    if not t or not await user_can_modify_task_async(actor_id,t): return False
    aid=str((assignee or {}).get("user_id") or "") or None
    if aid: await _ensure_user_async(aid)
    await _ensure_user_async(actor_id); now=_now()
    await transaction([("UPDATE tasks SET assignee_id=?,assignee_name=?,assignee_username=? WHERE id=?",(aid,(assignee or {}).get("display_name") or "",(assignee or {}).get("username") or "",task_id)),("""INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)""",(task_id,str(actor_id),action,t.get("assignee_name") or "",(assignee or {}).get("display_name") or "",now))]); return True
async def get_unassigned_tasks_async(user_id): return [t for t in await get_active_tasks_async(user_id) if not t.get("assignee_id")]
async def get_task_comments_async(task_id):
    from services.comment_message_store import get_comment_messages_async
    return await get_comment_messages_async(task_id, invalid_content_logger=logger, row_fetcher=fetch_all)

async def add_task_comment_async(task_id,author,content):
    if not await get_task_by_id_async(task_id): return False
    aid=str(author.get("id") or author.get("user_id") or "") or None
    if aid: await _ensure_user_async(aid)
    from services.comment_message_store import add_comment_async
    return await add_comment_async(task_id, author, content)
async def link_user_category_to_team_async(user_id,category,team_id):
    statements=[("UPDATE tasks SET team_id=? WHERE id=?",(team_id,t["id"])) for t in await get_all_user_tasks_async(user_id) if not t.get("team_id") and (t.get("category") or "").strip().lower()==(category or "").strip().lower()]
    if statements: await transaction(statements)
    return len(statements)
async def link_team_name_category_for_owner_async(team_id):
    team=await aget_team(team_id); return await link_user_category_to_team_async(team["owner_id"],team["name"],team_id) if team else 0
async def get_assignment_history_async(task_id): return await fetch_all("task_assignment_history","task_id=? ORDER BY id",(task_id,))

def _run(coro): return db_run(coro)
def read_tasks(): return _run(read_tasks_async())
def save_task(data): return _run(save_task_async(data))
def update_task_status(task_id,new_status,actor_id): return _run(update_task_status_async(task_id,new_status,actor_id))
def create_task(*a,**k): return _run(create_task_async(*a,**k))
def update_task(*a,**k): return _run(update_task_async(*a,**k))
def get_active_tasks(*a,**k): return _run(get_active_tasks_async(*a,**k))
def get_all_user_tasks(*a,**k): return _run(get_all_user_tasks_async(*a,**k))
def get_team_tasks(*a,**k): return _run(get_team_tasks_async(*a,**k))
def get_task_by_id(*a,**k): return _run(get_task_by_id_async(*a,**k))
def user_can_modify_task(*a,**k): return _run(user_can_modify_task_async(*a,**k))
def change_task_status(*a,**k): return _run(change_task_status_async(*a,**k))
def search_tasks(*a,**k): return _run(search_tasks_async(*a,**k))
def get_all_user_ids(): return _run(get_all_user_ids_async())
def assign_task(*a,**k): return _run(assign_task_async(*a,**k))
def get_unassigned_tasks(*a,**k): return _run(get_unassigned_tasks_async(*a,**k))
def get_task_comments(*a,**k): return _run(get_task_comments_async(*a,**k))
def get_parent_task(*a,**k): return _run(get_parent_task_async(*a,**k))
def create_child_task(*a,**k): return _run(create_child_task_async(*a,**k))
def list_child_tasks(*a,**k): return _run(list_child_tasks_async(*a,**k))
def count_child_tasks(*a,**k): return _run(count_child_tasks_async(*a,**k))
def move_child_task(*a,**k): return _run(move_child_task_async(*a,**k))
def archive_task(*a,**k): return _run(archive_task_async(*a,**k))
def unarchive_task(*a,**k): return _run(unarchive_task_async(*a,**k))
def add_task_comment(*a,**k): return _run(add_task_comment_async(*a,**k))
def link_user_category_to_team(*a,**k): return _run(link_user_category_to_team_async(*a,**k))
def link_team_name_category_for_owner(*a,**k): return _run(link_team_name_category_for_owner_async(*a,**k))
def get_assignment_history(*a,**k): return _run(get_assignment_history_async(*a,**k))
