"""Clinic metrics derived from scoped database facts, never AI estimates."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median

from services.database import fetch_all_sql, fetch_one_sql, transaction
from services.healthcare.access import Scope
from services.healthcare.service import audit, now


async def metrics(scope: Scope, *, unit_id=None, branch_id=None):
    if unit_id and branch_id and unit_id != branch_id:
        raise ValueError("conflicting_branch")
    unit_id = unit_id or branch_id
    pred, params = await scope.predicate("reports.view")
    if unit_id:
        pred += " AND e.unit_id=?"
        params += (unit_id,)
    stamp = now()
    tasks = await fetch_one_sql(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN e.assignee_id IS NOT NULL THEN 1 ELSE 0 END) AS with_owner, SUM(CASE WHEN e.deadline!='' THEN 1 ELSE 0 END) AS with_due, SUM(CASE WHEN e.status='done' THEN 1 ELSE 0 END) AS completed, SUM(CASE WHEN e.status IN ('pending','in_progress') AND e.deadline!='' AND e.deadline<? THEN 1 ELSE 0 END) AS overdue FROM tasks e WHERE {pred}",  # nosec B608
        (stamp,) + params,
    )  # nosec B608
    cases = await fetch_one_sql(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN e.status='blocked' THEN 1 ELSE 0 END) AS blocked, SUM(CASE WHEN e.status='active' AND NOT EXISTS(SELECT 1 FROM tasks t WHERE t.id=e.next_action_task_id AND t.case_id=e.id AND t.workspace_id=e.workspace_id AND t.status IN ('pending','in_progress')) THEN 1 ELSE 0 END) AS missing_next_action, SUM(CASE WHEN e.expected_at<? AND e.status NOT IN ('completed','closed','cancelled') THEN 1 ELSE 0 END) AS expected_overdue FROM cases e WHERE {pred}",  # nosec B608
        (stamp,) + params,
    )  # nosec B608
    counts = await fetch_one_sql(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN e.completed_at IS NOT NULL THEN 1 ELSE 0 END) AS completed, SUM(CASE WHEN e.status IN ('due','in_progress') AND e.due_at<? THEN 1 ELSE 0 END) AS overdue FROM followups e WHERE {pred}",  # nosec B608
        (stamp,) + params,
    )  # nosec B608
    delays = await fetch_all_sql(
        f"SELECT e.due_at,e.completed_at FROM followups e WHERE {pred} AND e.completed_at IS NOT NULL",  # nosec B608
        params,
    )  # nosec B608
    delay_seconds = [
        max(
            0,
            (
                datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
                - datetime.fromisoformat(r["due_at"].replace("Z", "+00:00"))
            ).total_seconds(),
        )
        for r in delays
    ]
    for result in (tasks, cases, counts):
        for key in result:
            result[key] = int(result[key] or 0)
    counts["completion_rate"] = (
        counts["completed"] / counts["total"] if counts["total"] else None
    )
    counts["median_delay_seconds"] = median(delay_seconds) if delay_seconds else None
    counts["delay_sample_size"] = len(delay_seconds)
    workload = await fetch_all_sql(
        f"SELECT e.assignee_id AS owner_id,COUNT(*) AS open_tasks FROM tasks e WHERE {pred} AND e.status IN ('pending','in_progress') GROUP BY e.assignee_id ORDER BY open_tasks DESC",  # nosec B608
        params,
    )  # nosec B608
    await transaction(
        [
            audit(
                scope,
                unit_id,
                "dashboard.viewed",
                "workspace",
                scope.workspace_id,
            )
        ]
    )
    return {
        "schema_version": 1,
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": tasks,
        "cases": cases,
        "followups": counts,
        "workload": workload,
    }
