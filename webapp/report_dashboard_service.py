from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta, timezone
from statistics import mean

from .reports import _access, _change, _jmonth, _priority, _status, _task_rows, _week, _habits, _recent
from .activity_feed import activity_feed

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


def _decode_filters(search: str) -> tuple[str, dict]:
    """Keep the existing `search` API backward compatible while allowing structured filters."""
    if not search:
        return "", {}
    raw = search.strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return str(data.get("q") or "").strip(), data
        except (TypeError, ValueError):
            pass
    return raw, {"q": raw}


def _query_tasks(access, start: date, end: date, search: str = "", filters: dict | None = None):
    query, structured = _decode_filters(search) if filters is None else (str(filters.get("q") or "").strip(), filters)
    where = "created_at>=? AND created_at<?"
    params = [start.isoformat(), (end + timedelta(days=1)).isoformat()]

    if query:
        normalized = STATUS_ALIASES.get(query.lower(), query)
        like = f"%{normalized}%"
        where += " AND (title LIKE ? OR id LIKE ? OR category LIKE ? OR status LIKE ? OR priority LIKE ? OR assignee_name LIKE ? OR assignee_username LIKE ? OR tags LIKE ?)"
        params.extend([like] * 8)

    status = STATUS_ALIASES.get(str(structured.get("status") or "").strip().lower(), str(structured.get("status") or "").strip())
    priority = str(structured.get("priority") or "").strip().lower()
    category = str(structured.get("category") or "").strip()
    assignee = str(structured.get("assignee") or "").strip()
    has_deadline = str(structured.get("has_deadline") or "").strip().lower()
    overdue = str(structured.get("overdue") or "").strip().lower()

    if status:
        where += " AND status=?"
        params.append(status)
    if priority:
        where += " AND priority=?"
        params.append(priority)
    if category:
        where += " AND category=?"
        params.append(category)
    if assignee:
        where += " AND (CAST(assignee_id AS TEXT)=? OR assignee_name=? OR assignee_username=?)"
        params.extend([assignee, assignee, assignee])
    if has_deadline == "yes":
        where += " AND deadline IS NOT NULL AND deadline!=''"
    elif has_deadline == "no":
        where += " AND (deadline IS NULL OR deadline='')"
    if overdue in {"yes", "no"}:
        today = datetime.now(timezone.utc).date().isoformat()
        clause = "deadline IS NOT NULL AND deadline!='' AND substr(deadline,1,10)<? AND status NOT IN ('done','cancelled','canceled')"
        where += f" AND ({clause if overdue == 'yes' else f'NOT ({clause})'})"
        params.append(today)
    return _task_rows(access, where, tuple(params))


def _filter_options(tasks):
    categories = sorted({str(t.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for t in tasks}, key=str.casefold)
    assignees = {}
    for task in tasks:
        aid = str(task.get("assignee_id") or "").strip()
        name = str(task.get("assignee_name") or task.get("assignee_username") or "").strip()
        username = str(task.get("assignee_username") or "").strip()
        key = aid or username or name
        if key and name:
            assignees[key] = {"value": key, "label": name, "username": username}
    return {
        "status": [{"value": "pending", "label": _status("pending")}, {"value": "in_progress", "label": _status("in_progress")}, {"value": "done", "label": _status("done")}, {"value": "cancelled", "label": _status("cancelled")}],
        "priority": [{"value": "high", "label": _priority("high")}, {"value": "medium", "label": _priority("medium")}, {"value": "low", "label": _priority("low")}],
        "category": [{"value": x, "label": x} for x in categories],
        "assignee": sorted(assignees.values(), key=lambda x: x["label"].casefold()),
        "has_deadline": [{"value": "yes", "label": "دارای مهلت"}, {"value": "no", "label": "بدون مهلت"}],
        "overdue": [{"value": "yes", "label": "عقب‌افتاده"}, {"value": "no", "label": "غیرعقب‌افتاده"}],
    }


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


def _previous_period(start: date, end: date) -> tuple[date, date]:
    """Shift the selected interval one calendar month back while preserving its duration."""
    target_year = start.year if start.month > 1 else start.year - 1
    target_month = start.month - 1 if start.month > 1 else 12
    target_day = min(start.day, calendar.monthrange(target_year, target_month)[1])
    previous_start = date(target_year, target_month, target_day)
    return previous_start, previous_start + (end - start)


def dashboard_report(token: str, section: str | None = None, page: int = 1, page_size: int = 25,
                     period: str = "month", start_value: str | None = None, end_value: str | None = None,
                     search: str = ""):
    access = _access(token)
    if not access:
        return None
    start, end = resolve_period(period, start_value, end_value)
    query, filters = _decode_filters(search)
    base_tasks = _query_tasks(access, start, end, query, {"q": query})
    tasks = _query_tasks(access, start, end, query, filters)
    statuses, priorities, categories = {}, {}, {}
    for task in tasks:
        status = task.get("status") or "pending"
        priority = task.get("priority") or "medium"
        category = (task.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی"
        statuses[status] = statuses.get(status, 0) + 1
        priorities[priority] = priorities.get(priority, 0) + 1
        categories[category] = categories.get(category, 0) + 1
    total = len(tasks)
    done = statuses.get("done", 0)
    cancelled = statuses.get("cancelled", statuses.get("canceled", 0))
    deadline_tasks = [task for task in tasks if task.get("deadline")]
    today = datetime.now(timezone.utc).date().isoformat()
    overdue = sum(1 for task in deadline_tasks if str(task.get("deadline"))[:10] < today and task.get("status") not in {"done", "cancelled", "canceled"})
    previous_start, previous_end = _previous_period(start, end)
    previous_total = len(_query_tasks(access, previous_start, previous_end, "", {}))
    result = {
        "report_type": "dashboard",
        "filter": {"period": period, "start": start.isoformat(), "end": end.isoformat(), "search": query, "filters": filters},
        "filter_options": _filter_options(base_tasks),
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
        total_rows = len(rows); page = max(1, int(page)); start_index = (page - 1) * page_size
        result.update({"section": section, "rows": rows[start_index:start_index + page_size], "page": page, "page_size": page_size,
                       "total": total_rows, "pages": max(1, (total_rows + page_size - 1) // page_size)})
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
        return {"section": section, "columns": columns, "total": sum(len(v) for v in columns.values()), "filter_options": result["filter_options"]}
    if section == "habits":
        result["habits"] = _habits(access, start, end); return result
    if section in {"recent_changes", "activity_feed"}:
        return activity_feed(access, start, end, query)
    if section == "heatmap":
        counts = {}
        for task in tasks:
            key = str(task.get("deadline") or "")[:10]
            if key: counts[key] = counts.get(key, 0) + 1
        cursor, days = start, []
        while cursor <= end:
            days.append({"day": cursor.day, "date": cursor.isoformat(), "count": counts.get(cursor.isoformat(), 0)}); cursor += timedelta(days=1)
        return {"section": section, "days": days, "max_count": max((x["count"] for x in days), default=0), "total": sum(counts.values())}
    if section == "week":
        data = _week(access)
        for day in data.get("week", {}).get("days", []):
            rows = [row for row in day.get("rows", []) if start.isoformat() <= day.get("date", "") <= end.isoformat()]
            if query:
                needle = query.lower(); rows = [row for row in rows if needle in str(row.get("title", "")).lower() or needle in str(row.get("id", "")).lower() or needle in str(row.get("category", "")).lower()]
            day["rows"], day["count"] = rows, len(rows)
        data["week"]["total"] = sum(day["count"] for day in data["week"]["days"]); return data
    return result
