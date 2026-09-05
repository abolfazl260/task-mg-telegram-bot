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

SORT_OPTIONS = {
    "newest": "جدیدترین",
    "oldest": "قدیمی‌ترین",
    "overdue": "بیشترین تأخیر",
    "priority": "بالاترین اولویت",
    "duration": "طولانی‌ترین زمان انجام",
}

JALALI_MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

IRANIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Convert Gregorian year, month, day to Jalali (Solar Hijri) calendar year, month, day."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def _parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, TypeError):
        return fallback


def _previous_period(start: date, end: date) -> tuple[date, date]:
    """Shift the selected interval one calendar month back while preserving its duration."""
    target_year = start.year if start.month > 1 else start.year - 1
    target_month = start.month - 1 if start.month > 1 else 12
    target_day = min(start.day, calendar.monthrange(target_year, target_month)[1])
    previous_start = date(target_year, target_month, target_day)
    return previous_start, previous_start + (end - start)


def resolve_period(period: str, start_value: str | None = None, end_value: str | None = None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    if period == "today":
        return today, today
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "custom":
        start = _parse_date(start_value, today)
        end = _parse_date(end_value, today)
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


def _parse_datetime(value: str | None):
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
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


def _productivity_metrics(tasks, now=None) -> dict:
    """Calculate Lead Time, Cycle Time, and On-time vs Overdue rates."""
    now = now or datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    
    durations_days = []
    completed_with_deadline = 0
    completed_on_time = 0
    completed_late = 0
    
    total_with_deadline = 0
    open_overdue = 0
    open_on_track = 0

    for task in tasks:
        status = (task.get("status") or "").lower()
        is_completed = status in {"done", "completed"}
        deadline_raw = str(task.get("deadline") or "").strip()
        deadline_date_str = deadline_raw[:10] if len(deadline_raw) >= 10 else ""
        
        created = _parse_datetime(task.get("created_at"))
        completed = _parse_datetime(task.get("completed_at"))
        
        if is_completed and created and completed and completed >= created:
            durations_days.append((completed - created).total_seconds() / 86400.0)
            
        if deadline_date_str:
            total_with_deadline += 1
            if is_completed:
                completed_with_deadline += 1
                completed_date_str = completed.date().isoformat() if completed else (str(task.get("completed_at") or "").strip())[:10]
                if not completed_date_str or completed_date_str <= deadline_date_str:
                    completed_on_time += 1
                else:
                    completed_late += 1
            elif status not in {"cancelled", "canceled"}:
                if deadline_date_str < today_str:
                    open_overdue += 1
                else:
                    open_on_track += 1

    avg_lead_time_days = round(mean(durations_days), 1) if durations_days else None
    avg_lead_time_hours = round(avg_lead_time_days * 24, 1) if avg_lead_time_days is not None else None
    
    on_time_rate = round(completed_on_time / completed_with_deadline * 100) if completed_with_deadline > 0 else (100 if completed_with_deadline == 0 and not open_overdue else 0)
    overdue_rate = round(completed_late / completed_with_deadline * 100) if completed_with_deadline > 0 else 0
    
    return {
        "lead_time_days": avg_lead_time_days,
        "lead_time_hours": avg_lead_time_hours,
        "cycle_time_days": avg_lead_time_days,
        "completed_with_deadline": completed_with_deadline,
        "completed_on_time": completed_on_time,
        "completed_late": completed_late,
        "on_time_rate": on_time_rate,
        "overdue_rate": overdue_rate,
        "open_overdue": open_overdue,
        "open_on_track": open_on_track,
        "total_with_deadline": total_with_deadline,
    }


def _heatmap_data(tasks, start: date, end: date) -> dict:
    """Build a GitHub-style activity contribution calendar using Jalali dates."""
    created_counts: dict[str, int] = {}
    completed_counts: dict[str, int] = {}
    deadline_counts: dict[str, int] = {}
    
    for task in tasks:
        c_date = str(task.get("created_at") or "")[:10]
        if c_date:
            created_counts[c_date] = created_counts.get(c_date, 0) + 1
        status = (task.get("status") or "").lower()
        if status in {"done", "completed"}:
            comp_date = str(task.get("completed_at") or "")[:10]
            if comp_date:
                completed_counts[comp_date] = completed_counts.get(comp_date, 0) + 1
        d_date = str(task.get("deadline") or "")[:10]
        if d_date:
            deadline_counts[d_date] = deadline_counts.get(d_date, 0) + 1

    cursor = start
    days = []
    while cursor <= end:
        iso = cursor.isoformat()
        c_cnt = created_counts.get(iso, 0)
        done_cnt = completed_counts.get(iso, 0)
        dl_cnt = deadline_counts.get(iso, 0)
        total_activity = c_cnt + done_cnt
        
        jy, jm, jd = gregorian_to_jalali(cursor.year, cursor.month, cursor.day)
        jalali_str = f"{jy:04d}/{jm:02d}/{jd:02d}"
        weekday = (cursor.weekday() + 2) % 7  # 0=Saturday, 6=Friday
        weekday_name = IRANIAN_WEEKDAYS[weekday]
        
        daily_rate = round(done_cnt / total_activity * 100) if total_activity > 0 else (100 if done_cnt > 0 else 0)
        
        days.append({
            "date": iso,
            "day": cursor.day,
            "jalali_date": jalali_str,
            "jalali_day": jd,
            "jalali_month": jm,
            "jalali_month_name": JALALI_MONTH_NAMES[jm],
            "jalali_year": jy,
            "weekday": weekday,
            "weekday_name": weekday_name,
            "created": c_cnt,
            "completed": done_cnt,
            "deadlines": dl_cnt,
            "count": total_activity,
            "activity": total_activity,
            "completion_rate": daily_rate,
        })
        cursor += timedelta(days=1)
        
    max_activity = max((d["activity"] for d in days), default=0)
    
    for d in days:
        act = d["activity"]
        if act == 0 or max_activity == 0:
            d["level"] = 0
        else:
            ratio = act / max_activity
            if ratio <= 0.25:
                d["level"] = 1
            elif ratio <= 0.50:
                d["level"] = 2
            elif ratio <= 0.75:
                d["level"] = 3
            else:
                d["level"] = 4

    busiest_days = sorted(
        [d for d in days if d["activity"] > 0],
        key=lambda x: (x["activity"], x["completed"]),
        reverse=True
    )[:5]
    
    total_created = sum(d["created"] for d in days)
    total_completed = sum(d["completed"] for d in days)
    active_days = sum(1 for d in days if d["activity"] > 0)
    overall_rate = round(total_completed / (total_created + total_completed) * 100) if (total_created + total_completed) > 0 else 0

    return {
        "section": "heatmap",
        "days": days,
        "max_count": max_activity,
        "total": sum(d["activity"] for d in days),
        "total_created": total_created,
        "total_completed": total_completed,
        "active_days": active_days,
        "busiest_days": busiest_days,
        "overall_completion_rate": overall_rate,
        "jalali_period": f"{days[0]['jalali_date']} تا {days[-1]['jalali_date']}" if days else "",
    }


def _duration_seconds(task):
    created = _parse_datetime(task.get("created_at"))
    completed = _parse_datetime(task.get("completed_at"))
    if not created or not completed or completed < created:
        return -1
    return (completed - created).total_seconds()


def _overdue_seconds(task, now=None):
    deadline = _parse_datetime(task.get("deadline"))
    if not deadline or (task.get("status") or "") in {"done", "completed", "cancelled", "canceled"}:
        return 0
    now = now or datetime.now(timezone.utc)
    return max(0, (now - deadline).total_seconds())


def _priority_rank(task):
    return {"high": 3, "medium": 2, "low": 1}.get(str(task.get("priority") or "medium").lower(), 0)


def _sort_tasks(tasks, sort_key="newest"):
    """Sort the complete filtered task set before pagination."""
    sort_key = sort_key if sort_key in SORT_OPTIONS else "newest"
    now = datetime.now(timezone.utc)
    if sort_key == "newest":
        return sorted(tasks, key=lambda x: (_parse_datetime(x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), str(x.get("id") or "")), reverse=True)
    if sort_key == "oldest":
        return sorted(tasks, key=lambda x: (_parse_datetime(x.get("created_at")) or datetime.max.replace(tzinfo=timezone.utc), str(x.get("id") or "")))
    if sort_key == "overdue":
        return sorted(tasks, key=lambda x: (_overdue_seconds(x, now), _parse_datetime(x.get("deadline")) or datetime.max.replace(tzinfo=timezone.utc)), reverse=True)
    if sort_key == "priority":
        return sorted(tasks, key=lambda x: (_priority_rank(x), _parse_datetime(x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return sorted(tasks, key=lambda x: (_duration_seconds(x), _parse_datetime(x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)


def _row(task):
    return {
        "id": task.get("id"), "title": task.get("title") or "بدون عنوان",
        "status": task.get("status") or "pending", "status_label": _status(task.get("status")),
        "priority": task.get("priority") or "medium", "priority_label": _priority(task.get("priority")),
        "deadline": task.get("deadline") or "", "category": task.get("category") or "—",
        "assignee": task.get("assignee_name") or task.get("assignee_username") or "بدون مسئول",
        "created_at": task.get("created_at") or "", "completed_at": task.get("completed_at") or "",
        "duration_seconds": _duration_seconds(task), "overdue_seconds": _overdue_seconds(task),
    }


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
    filtered_task_ids = {str(task.get("id")) for task in tasks}
    statuses, priorities, categories = {}, {}, {}
    for task in tasks:
        status = task.get("status") or "pending"
        priority = task.get("priority") or "medium"
        category = (task.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی"
        statuses[status] = statuses.get(status, 0) + 1
        priorities[priority] = priorities.get(priority, 0) + 1
        categories[category] = categories.get(category, 0) + 1
    total = len(tasks)
    done = statuses.get("done", 0) + statuses.get("completed", 0)
    cancelled = statuses.get("cancelled", statuses.get("canceled", 0))
    deadline_tasks = [task for task in tasks if task.get("deadline")]
    today = datetime.now(timezone.utc).date().isoformat()
    overdue = sum(1 for task in deadline_tasks if str(task.get("deadline"))[:10] < today and task.get("status") not in {"done", "cancelled", "canceled"})
    previous_start, previous_end = _previous_period(start, end)
    previous_total = len(_query_tasks(access, previous_start, previous_end, "", {}))
    productivity = _productivity_metrics(tasks)
    result = {
        "report_type": "dashboard",
        "filter": {"period": period, "start": start.isoformat(), "end": end.isoformat(), "search": query, "filters": filters},
        "filter_options": _filter_options(base_tasks),
        "sort_options": [{"value": k, "label": v} for k, v in SORT_OPTIONS.items()],
        "period": {"gregorian": f"{start.isoformat()} تا {end.isoformat()}", "jalali": _jmonth(start)},
        "summary": {
            "total": total, "total_change": _change(total, previous_total), "done": done,
            "in_progress": statuses.get("in_progress", 0), "pending": statuses.get("pending", 0),
            "cancelled": cancelled, "active": total - done - cancelled, "overdue": overdue,
            "with_deadline": len(deadline_tasks), "without_deadline": total - len(deadline_tasks),
            "completion_rate": round(done / total * 100) if total else 0,
            "average_completion_days": productivity["lead_time_days"],
            "lead_time_days": productivity["lead_time_days"],
            "lead_time_hours": productivity["lead_time_hours"],
            "cycle_time_days": productivity["cycle_time_days"],
            "on_time_rate": productivity["on_time_rate"],
            "overdue_rate": productivity["overdue_rate"],
            "completed_on_time": productivity["completed_on_time"],
            "completed_late": productivity["completed_late"],
            "productivity": productivity,
        },
        "by_status": [{"key": k, "label": _status(k), "count": v} for k, v in statuses.items()],
        "by_priority": [{"key": k, "label": _priority(k), "count": v} for k, v in priorities.items()],
        "by_category": [{"label": k, "count": v} for k, v in categories.items()],
    }
    if section is None:
        return result
    if section in {"tasks", "deadlines", "calendar"}:
        selected = [task for task in tasks if section == "tasks" or task.get("deadline")]
        sort_key = str(filters.get("sort") or "newest")
        selected = _sort_tasks(selected, sort_key)
        rows = [_row(task) for task in selected]
        total_rows = len(rows); page = max(1, int(page)); start_index = (page - 1) * page_size
        result.update({"section": section, "rows": rows[start_index:start_index + page_size], "page": page, "page_size": page_size,
                       "total": total_rows, "pages": max(1, (total_rows + page_size - 1) // page_size), "sort": sort_key})
        return result
    if section in {"status", "priority", "category"}:
        result["section"] = section
        rows = [{"key": k, "label": _status(k), "count": v} for k, v in statuses.items()] if section == "status" else (
            [{"key": k, "priority": _priority(k), "count": v} for k, v in priorities.items()] if section == "priority" else (
                [{"category": k, "count": v} for k, v in categories.items()]
            )
        )
        result["rows"] = rows; return result
    if section == "kanban":
        columns = {}
        for task in tasks:
            key = "cancelled" if task.get("status") in {"cancelled", "canceled"} else task.get("status") or "pending"
            columns.setdefault(key, []).append(_row(task))
        return {"section": section, "columns": columns, "total": sum(len(v) for v in columns.values()), "filter_options": result["filter_options"]}
    if section == "habits":
        result["habits"] = _habits(access, start, end); return result
    if section in {"recent_changes", "activity_feed"}:
        data = activity_feed(access, start, end, query)
        if filters and len(filters) > 1:
            data["events"] = [event for event in data.get("events", []) if str(event.get("task_id")) in filtered_task_ids]
            data["total"] = len(data["events"])
        return data
    if section == "heatmap":
        return _heatmap_data(tasks, start, end)
    if section == "week":
        data = _week(access)
        for day in data.get("week", {}).get("days", []):
            rows = [row for row in day.get("rows", []) if start.isoformat() <= day.get("date", "") <= end.isoformat()]
            if query:
                needle = query.lower(); rows = [row for row in rows if needle in str(row.get("title", "")).lower() or needle in str(row.get("id", "")).lower() or needle in str(row.get("category", "")).lower()]
            if filters and len(filters) > 1:
                rows = [row for row in rows if str(row.get("id")) in filtered_task_ids]
            day["rows"], day["count"] = rows, len(rows)
        data["week"]["total"] = sum(day["count"] for day in data["week"]["days"]); return data
    return result
