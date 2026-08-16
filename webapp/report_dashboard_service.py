from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from statistics import mean

from .reports import _access, _change, _jmonth, _priority, _status, _task_rows, _week, _habits, _recent


STATUS_ALIASES = {
    "انجام شده": "done", "انجام‌شده": "done", "انجام شده است": "done",
    "در حال انجام": "in_progress", "شروع نشده": "pending", "شروع‌نشده": "pending",
    "لغو شده": "cancelled", "لغوشده": "cancelled",
}


def _parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def resolve_period(period: str, start_value: str | None = None, end_value: str | None = None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    if period == "today":
        return today, today
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "custom":
        start = _parse_date(start_value, today)
        end = _parse_date(end_value, start)
        return (start, end) if start <= end else (end, start)
    return date(today.year, today.month, 1), date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])


def _query_tasks(access, start: date, end: date, search: str = ""):
    where = "created_at>=? AND created_at<?"
    params = [start.isoformat(), (end + timedelta(days=1)).isoformat()]
    if search:
        normalized = STATUS_ALIASES.get(search.strip().lower(), search.strip())
        like = f"%{normalized}%"
        where += " AND (title LIKE ? OR id LIKE ? OR category LIKE ? OR status LIKE ?)"
        params.extend([like, like, like, like])
    return _task_rows(access, where, tuple(params))


def _parse_datetime(value: str):
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _average_completion(tasks) -> float | None:
    durations = []
    for task in tasks:
        if (task.get("status") or "") not in {"done", "completed"}:
            continue
        created = _parse_datetime(task.get("created_at"))
        completed = _parse_datetime(task.get("completed_at"))
        if not created or not completed or completed < created:
            continue
        durations.append((completed - created).total_seconds() / 86400)
    return round(mean(durations), 1) if durations else None


def _row(task):
    return {
        "id": task.get("id"), "title": task.get("title") or "بدون عنوان",
        "status": task.get("status") or "pending", "status_label": _status(task.get("status")),
        "priority": task.get("priority") or "medium", "priority_label": _priority(task.get("priority")),
        "deadline": task.get("deadline") or "", "category": task.get("category") or "—",
        "assignee": task.get("assignee_name") or task.get("assignee_username") or "بدون مسئول",
    }


def dashboard_report(token: str, section: str | None = None, page: int = 1, page_size: int = 25,
                     period: str = "month", start_value: str | None = None, end_value: str | None = None,
                     search: str = ""):
    access = _access(token)
    if not access:
        return None
    start, end = resolve_period(period, start_value, end_value)
    tasks = _query_tasks(access, start, end, search)
    statuses = {}
    priorities = {}
    categories = {}
    for task in tasks:
        statuses[task.get("status") or "pending"] = statuses.get(task.get("status") or "pending", 0) + 1
        priorities[task.get("priority") or "medium"] = priorities.get(task.get("priority") or "medium", 0) + 1
        category = (task.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی"
        categories[category] = categories.get(category, 0) + 1
    total = len(tasks)
    done = statuses.get("done", 0)
    cancelled = statuses.get("cancelled", statuses.get("canceled", 0))
    deadline_tasks = [task for task in tasks if task.get("deadline")]
    today = datetime.now(timezone.utc).date().isoformat()
    overdue = sum(1 for task in deadline_tasks if str(task.get("deadline"))[:10] < today and task.get("status") not in {"done", "cancelled", "canceled"})

    previous_start = start.replace(day=1) - timedelta(days=1)
    previous_start = previous_start.replace(day=1)
    previous_end = start - timedelta(days=1)
    previous_total = len(_query_tasks(access, previous_start, previous_end, ""))
    result = {
        "report_type": "dashboard", "filter": {"period": period, "start": start.isoformat(), "end": end.isoformat(), "search": search},
        "period": {"gregorian": f"{start.isoformat()} تا {end.isoformat()}", "jalali": _jmonth(start)},
        "summary": {
            "total": total, "total_change": _change(total, previous_total), "done": done,
            "in_progress": statuses.get("in_progress", 0), "pending": statuses.get("pending", 0),
            "cancelled": cancelled, "completion_rate": round(done / total * 100) if total else 0,
            "overdue": overdue, "with_deadline": len(deadline_tasks), "without_deadline": total - len(deadline_tasks),
            "average_completion_days": _average_completion(tasks),
        },
        "by_status": [{"key": k, "label": _status(k), "count": v} for k, v in sorted(statuses.items(), key=lambda x: -x[1])],
        "by_priority": [{"key": k, "label": _priority(k), "count": v} for k, v in sorted(priorities.items(), key=lambda x: -x[1])],
        "by_category": [{"label": k, "count": v} for k, v in sorted(categories.items(), key=lambda x: -x[1])],
    }
    if not section:
        return result
    if section in {"tasks", "deadlines", "calendar"}:
        selected = [task for task in tasks if section == "tasks" or task.get("deadline")]
        selected.sort(key=lambda x: x.get("deadline") or "9999")
        rows = [_row(task) for task in selected]
        total_rows = len(rows)
        page = max(1, int(page))
        start_index = (page - 1) * page_size
        result.update({"section": section, "rows": rows[start_index:start_index + page_size], "page": page,
                       "page_size": page_size, "total": total_rows, "pages": max(1, (total_rows + page_size - 1) // page_size)})
        return result
    if section in {"status", "priority", "category"}:
        result["section"] = section
        result["rows"] = result["by_status"] if section == "status" else result["by_priority"] if section == "priority" else [{"category": x["label"], "count": x["count"]} for x in result["by_category"]]
        return result
    if section == "kanban":
        columns = {"pending": [], "in_progress": [], "done": [], "cancelled": []}
        for task in tasks:
            key = "cancelled" if task.get("status") in {"cancelled", "canceled"} else task.get("status") or "pending"
            columns.setdefault(key, []).append(_row(task))
        return {"section": section, "columns": columns, "total": sum(len(v) for v in columns.values())}
    if section == "habits":
        result["habits"] = _habits(access, start, end)
        return result
    if section == "recent_changes":
        data = _recent(access)
        events = [event for event in data.get("events", []) if start.isoformat() <= str(event.get("created_at", ""))[:10] <= end.isoformat()]
        if search:
            needle = search.lower()
            events = [event for event in events if needle in str(event.get("task_title", "")).lower() or needle in str(event.get("task_id", "")).lower()]
        data["events"] = events
        data["total"] = len(events)
        return data
    if section == "heatmap":
        counts = {}
        for task in tasks:
            key = str(task.get("deadline") or "")[:10]
            if key:
                counts[key] = counts.get(key, 0) + 1
        cursor = start
        days = []
        while cursor <= end:
            days.append({"day": cursor.day, "date": cursor.isoformat(), "count": counts.get(cursor.isoformat(), 0)})
            cursor += timedelta(days=1)
        return {"section": section, "days": days, "max_count": max((x["count"] for x in days), default=0), "total": sum(counts.values())}
    if section == "week":
        data = _week(access)
        filtered_days = []
        for day in data.get("week", {}).get("days", []):
            rows = [row for row in day.get("rows", []) if start.isoformat() <= day.get("date", "") <= end.isoformat()]
            if search:
                needle = search.lower()
                rows = [row for row in rows if needle in str(row.get("title", "")).lower() or needle in str(row.get("id", "")).lower() or needle in str(row.get("category", "")).lower()]
            day["rows"] = rows
            day["count"] = len(rows)
            filtered_days.append(day)
        data["week"]["days"] = filtered_days
        data["week"]["total"] = sum(day["count"] for day in filtered_days)
        return data
    return result
