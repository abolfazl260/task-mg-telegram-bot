"""SQL-backed Task/Attribute/Contact search with permission predicates."""
from __future__ import annotations

from services.database import fetch_all_sql

SORTS = {
    "created_at": "t.created_at", "title": "t.title", "deadline": "t.deadline",
    "status": "t.status", "priority": "t.priority", "work_item_type": "t.work_item_type",
}


async def query_tasks_async(actor_id, *, query="", work_item_type=None, parent_task_id=None,
                            status=None, owner_id=None, workspace_id=None, contact_query=None,
                            attribute_filters=None, sort="created_at", descending=True,
                            limit=50, offset=0):
    try:
        limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_pagination") from exc
    order = SORTS.get(sort)
    if not order: raise ValueError("invalid_sort")
    clauses = ["(t.workspace_id IS NULL AND t.user_id=? OR t.workspace_id IS NOT NULL AND EXISTS (SELECT 1 FROM workspace_memberships wm WHERE wm.workspace_id=t.workspace_id AND wm.user_id=? AND wm.status='active'))"]
    params = [str(actor_id), str(actor_id)]
    if workspace_id is None: clauses.append("t.workspace_id IS NULL")
    else: clauses.append("t.workspace_id=?"); params.append(str(workspace_id))
    if query:
        clauses.append("(LOWER(t.title) LIKE ? OR LOWER(t.description) LIKE ? OR LOWER(t.category) LIKE ? OR LOWER(t.tags) LIKE ?)")
        q = f"%{str(query).strip().lower()}%"; params += [q, q, q, q]
    for column, value in (("t.work_item_type", work_item_type), ("t.parent_task_id", parent_task_id), ("t.status", status), ("t.user_id", owner_id)):
        if value is not None: clauses.append(f"{column}=?"); params.append(str(value))
    if contact_query:
        clauses.append("EXISTS (SELECT 1 FROM task_contact_points cp WHERE cp.task_id=t.id AND cp.status='active' AND cp.normalized_value LIKE ?)")
        params.append(f"%{str(contact_query).strip().casefold()}%")
    for key, expected in (attribute_filters or {}).items():
        if not isinstance(key, str) or not key: raise ValueError("invalid_attribute_filter")
        clauses.append("EXISTS (SELECT 1 FROM task_attribute_values av JOIN task_attribute_definitions ad ON ad.id=av.definition_id WHERE av.task_id=t.id AND ad.field_key=? AND ad.active=1 AND (av.value_text=? OR av.value_number=? OR av.value_date=? OR av.value_datetime=? OR av.value_json=?))")
        params += [key, str(expected), expected if isinstance(expected, (int, float)) and not isinstance(expected, bool) else None, str(expected), str(expected), str(expected)]
    params += [limit, offset]
    return await fetch_all_sql("SELECT t.* FROM tasks t WHERE " + " AND ".join(clauses) + f" ORDER BY {order} {'DESC' if descending else 'ASC'}, t.id LIMIT ? OFFSET ?", tuple(params))


query_tasks = lambda *a, **k: __import__("services.database", fromlist=["_run"])._run(query_tasks_async(*a, **k))
