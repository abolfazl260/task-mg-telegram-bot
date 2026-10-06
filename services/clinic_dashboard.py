"""Clinic dashboard metrics built from the generic scope predicates."""
from __future__ import annotations

from services.database import fetch_all_sql, fetch_one_sql
from services.work_item_access import workspace_predicate


async def dashboard_async(workspace_id: str, actor_id: str, *, branch_id: str | None = None) -> dict:
    task_pred, task_args = await workspace_predicate(workspace_id, actor_id, alias='t', action='view')
    branch_clause_t = ' AND t.unit_id=?' if branch_id else ''
    b = [branch_id] if branch_id else []
    async def count(table, pred, args, extra='', suffix=''):
        row = await fetch_one_sql(f'SELECT COUNT(*) AS n FROM {table} {suffix} WHERE {pred}{extra}', tuple(args)+tuple(b))
        return int((row or {}).get('n') or 0)
    patients = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='patient'", 't')
    sessions_today = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='session' AND substr(COALESCE(t.deadline,''),1,10)=date('now')", 't')
    sessions_completed = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='session' AND t.status='completed'", 't')
    sessions_cancelled = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='session' AND t.status IN ('cancelled','no_show')", 't')
    followups_due = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='followup' AND t.status IN ('due','in_progress') AND t.deadline<=datetime('now')", 't')
    followups_overdue = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='followup' AND t.status IN ('due','in_progress') AND t.deadline<datetime('now')", 't')
    without_next = await count('tasks', task_pred, task_args, branch_clause_t + " AND t.work_item_type='patient' AND NOT EXISTS (SELECT 1 FROM tasks child WHERE child.parent_task_id=t.id AND child.work_item_type IN ('session','followup') AND child.status NOT IN ('completed','cancelled','closed'))", 't')
    by_doctor = await fetch_all_sql(f"SELECT t.assignee_id AS doctor_id,COUNT(*) AS sessions FROM tasks t WHERE {task_pred}{branch_clause_t} AND t.work_item_type='session' GROUP BY t.assignee_id ORDER BY sessions DESC", tuple(task_args)+tuple(b))
    return {'patients': {'total': patients}, 'sessions': {'today': sessions_today, 'completed': sessions_completed, 'cancelled_or_no_show': sessions_cancelled}, 'followups': {'due': followups_due, 'overdue': followups_overdue}, 'patients_without_next_action': without_next, 'workload_by_doctor': by_doctor}


def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)

dashboard = lambda *a, **k: _run(dashboard_async(*a, **k))
