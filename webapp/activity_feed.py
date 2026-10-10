"""Activity feed aggregation for the web reporting dashboard.

This module intentionally derives the feed from existing task, comment and
assignment-history records. It does not change the database schema or mutate
any existing task/report data.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.database import sync_all


def _parse(value):
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _event(event_id, kind, icon, title, task, actor="کاربر", text="", created_at=""):
    return {
        "id": event_id,
        "type": kind,
        "icon": icon,
        "title": title,
        "task_id": task.get("id"),
        "task_title": task.get("title") or "بدون عنوان",
        "actor": actor or "کاربر",
        "text": text or "",
        "created_at": created_at or "",
    }


def activity_feed(access, start=None, end=None, query="", limit=100):
    args = (access["bot_key"], str(access["user_id"]))
    scope = "workspace_id IS NULL AND bot_key=? AND user_id=?"

    def date_clause(field):
        if field not in {"created_at", "completed_at"}:
            raise ValueError("unsupported_report_time_field")
        # Use range predicates on raw ISO timestamps so SQLite can apply
        # indexes. Retain the old in_range check for unexpected date formats.
        clauses, values = [], []
        if start:
            clauses.append(f"{field}>=?")
            values.append(start.isoformat())
        if end:
            clauses.append(f"{field}<?")
            values.append((end + timedelta(days=1)).isoformat())
        return " AND ".join(clauses) if clauses else "1=1", tuple(values)

    created_sql, created_params = date_clause("created_at")
    completed_sql, completed_params = date_clause("completed_at")
    tasks = sync_all(
        "tasks",
        f"{scope} AND (({created_sql}) OR ({completed_sql}))",
        args + created_params + completed_params,
    )
    task_map = {str(task.get("id")): task for task in tasks}
    events = []

    def in_range(value):
        if not value:
            return False
        day = str(value)[:10]
        return (not start or day >= start.isoformat()) and (not end or day <= end.isoformat())

    def matches(event):
        if not query:
            return True
        needle = query.casefold()
        return any(
            needle in str(event.get(key) or "").casefold()
            for key in ("task_id", "task_title", "actor", "text", "title")
        )

    for task in tasks:
        created_at = task.get("created_at") or ""
        if in_range(created_at):
            events.append(_event(
                f"task-created-{task.get('id')}", "task_created", "➕", "تسک ایجاد شد",
                task, task.get("creator_name") or task.get("created_by_name") or "کاربر",
                "", created_at,
            ))
        completed_at = task.get("completed_at") or ""
        if completed_at and in_range(completed_at):
            events.append(_event(
                f"task-completed-{task.get('id')}", "task_completed", "✅", "تسک تکمیل شد",
                task, task.get("assignee_name") or "کاربر", "", completed_at,
            ))

    try:
        comment_sql, comment_params = date_clause("created_at")
        comments = sync_all(
            "task_comments",
            f"task_id IN (SELECT id FROM tasks WHERE {scope}) AND ({comment_sql})",  # nosec B608 - constant scope and allowlisted column, bound values
            args + comment_params,
        )
    except Exception:
        comments = []

    try:
        assignment_sql, assignment_params = date_clause("created_at")
        assignments = sync_all(
            "task_assignment_history",
            f"task_id IN (SELECT id FROM tasks WHERE {scope}) AND ({assignment_sql})",  # nosec B608 - constant scope and allowlisted column, bound values
            args + assignment_params,
        )
    except Exception:
        assignments = []

    comment_labels = {
        "text": "کامنت ثبت کرد",
        "photo": "تصویر ارسال کرد",
        "voice": "پیام صوتی ارسال کرد",
        "audio": "فایل صوتی ارسال کرد",
        "document": "فایل ارسال کرد",
        "video": "ویدئو ارسال کرد",
        "animation": "گیف ارسال کرد",
        "sticker": "استیکر ارسال کرد",
    }
    # Comments/assignments can refer to tasks created before the selected
    # period. Retrieve metadata for those specific IDs rather than every task.
    missing_ids = {
        str(row.get("task_id")) for row in comments + assignments if row.get("task_id")
    } - task_map.keys()
    missing = sorted(missing_ids)
    for offset in range(0, len(missing), 400):
        chunk = missing[offset:offset + 400]
        placeholders = ",".join("?" for _ in chunk)
        for task in sync_all("tasks", f"{scope} AND id IN ({placeholders})", args + tuple(chunk)):
            task_map[str(task.get("id"))] = task

    for row in comments:
        created_at = row.get("created_at") or ""
        if not in_range(created_at):
            continue
        try:
            content = json.loads(row.get("content_json") or "{}")
        except Exception:
            content = {}
        if not isinstance(content, dict):
            content = {"content": content}
        kind = content.get("type") or "text"
        text = content.get("text") or content.get("caption") or content.get("file_name") or "محتوا ارسال شد"
        task = task_map.get(str(row.get("task_id")), {})
        events.append(_event(
            f"comment-{row.get('id')}", "comment", "💬", comment_labels.get(kind, "کامنت ثبت کرد"),
            task, row.get("author_name") or row.get("author_username") or "کاربر",
            str(text).replace("\n", " ")[:220], created_at,
        ))

    for row in assignments:
        created_at = row.get("created_at") or ""
        if not in_range(created_at):
            continue
        task = task_map.get(str(row.get("task_id")), {})
        action = row.get("action") or "assigned"
        if action in ("unassigned", "removed"):
            title = "مسئولیت تسک را حذف کرد"
            text = f"مسئول قبلی: {row.get('old_assignee_name') or '—'}"
        elif action in ("claimed", "self_assigned"):
            title = "تسک را برای خود برداشت"
            text = f"مسئول: {row.get('new_assignee_name') or '—'}"
        else:
            title = "مسئول تسک را تغییر داد"
            text = f"{row.get('old_assignee_name') or 'بدون مسئول'} ← {row.get('new_assignee_name') or 'بدون مسئول'}"
        events.append(_event(
            f"assignment-{row.get('id')}", "assignment", "👤", title, task,
            row.get("actor_name") or row.get("actor_id") or "کاربر", text, created_at,
        ))

    events = [event for event in events if matches(event)]
    events.sort(
        key=lambda item: (_parse(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), item.get("id") or ""),
        reverse=True,
    )
    return {"section": "recent_changes", "total": len(events), "events": events[:max(1, int(limit))]}
