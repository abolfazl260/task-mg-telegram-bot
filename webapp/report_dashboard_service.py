from __future__ import annotations

import calendar
import json
import re
from datetime import UTC, date, datetime, timedelta
from statistics import mean

import jdatetime

from services.database import sync_query_one

from .reports import _access, _change, _jmonth, _priority, _status, _task_rows, _task_scope, _week, _habits, _recent
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


# A leap-year-long export remains supported, but a multi-year heatmap is not.
# The date envelope prevents arithmetic overflows in previous-period
# comparisons and calendars at Python's minimum/maximum date boundaries.
MAX_REPORT_DAYS = 366
MIN_REPORT_DATE = date(1900, 1, 1)
MAX_REPORT_DATE = date(2100, 12, 31)
MAX_REPORT_PAGE = 10_000


def _parse_date(value: str | None) -> date:
    """Require one exact Gregorian YYYY-MM-DD; never silently use today."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("invalid_report_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid_report_date") from exc
    if not MIN_REPORT_DATE <= parsed <= MAX_REPORT_DATE:
        raise ValueError("report_date_out_of_range")
    return parsed


def validate_report_page(page: object) -> int:
    """Reject malformed, negative and excessive page numbers before DB work."""
    value = str(page)
    if not re.fullmatch(r"[0-9]{1,5}", value):
        raise ValueError("invalid_report_page")
    parsed = int(value)
    if not 1 <= parsed <= MAX_REPORT_PAGE:
        raise ValueError("invalid_report_page")
    return parsed


def _previous_period(start: date, end: date) -> tuple[date, date]:
    """Shift the selected interval one calendar month back while preserving its duration."""
    target_year = start.year if start.month > 1 else start.year - 1
    target_month = start.month - 1 if start.month > 1 else 12
    target_day = min(start.day, calendar.monthrange(target_year, target_month)[1])
    previous_start = date(target_year, target_month, target_day)
    return previous_start, previous_start + (end - start)


def resolve_period(period: str, start_value: str | None = None, end_value: str | None = None) -> tuple[date, date]:
    """Validate the same period contract for dashboard, sections and exports."""
    today = datetime.now(UTC).date()
    if period == "today":
        return today, today
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "month":
        return date(today.year, today.month, 1), date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    if period != "custom":
        raise ValueError("invalid_report_period")
    start, end = _parse_date(start_value), _parse_date(end_value)
    # Existing API behavior swaps reversed dates; keep that compatibility.
    if start > end:
        start, end = end, start
    if (end - start).days + 1 > MAX_REPORT_DAYS:
        raise ValueError("report_period_too_large")
    return start, end


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


def _task_predicate(access, start: date, end: date, search: str = "", filters: dict | None = None,
                    population: str = "created"):
    """Share report filters while keeping independent KPI populations."""
    query, structured = _decode_filters(search) if filters is None else (str(filters.get("q") or "").strip(), filters)
    if population == "created":
        where = "created_at>=? AND created_at<?"
        params = [start.isoformat(), (end + timedelta(days=1)).isoformat()]
    elif population == "completed":
        # Extend the indexed range by one day each side, then normalize
        # timezone-aware completion timestamps in Python for exact UTC bounds.
        where = "completed_at>=? AND completed_at<? AND status IN ('done','completed')"
        params = [(start - timedelta(days=1)).isoformat(), (end + timedelta(days=2)).isoformat()]
    elif population == "calendar":
        # Calendar is selected by due date, not by task creation date.
        # A date's full event list is needed, regardless of when it was created.
        where = "substr(deadline,1,10)>=? AND substr(deadline,1,10)<=?"
        params = [start.isoformat(), end.isoformat()]
    elif population == "open_backlog":
        # Current open backlog is independent of the selected creation period.
        # Exclude future-created records from the as-of-today snapshot.
        where = (
            "deadline IS NOT NULL AND deadline!='' AND "
            "status NOT IN ('done','completed','cancelled','canceled') AND "
            "(created_at IS NULL OR created_at='' OR created_at<?)"
        )
        params = [(end + timedelta(days=1)).isoformat()]
    else:
        raise ValueError("invalid_report_population")

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
        today = datetime.now(UTC).date().isoformat()
        clause = "deadline IS NOT NULL AND deadline!='' AND substr(deadline,1,10)<? AND status NOT IN ('done','cancelled','canceled')"
        where += f" AND ({clause if overdue == 'yes' else f'NOT ({clause})'})"
        params.append(today)
    return where, tuple(params)



def _query_tasks(access, start: date, end: date, search: str = "", filters: dict | None = None):
    where, params = _task_predicate(access, start, end, search, filters)
    return _task_rows(access, where, params)


def _query_calendar_tasks(access, start: date, end: date, search: str = "", filters: dict | None = None):
    """Select every authorized due-date event in the requested calendar range."""
    where, params = _task_predicate(access, start, end, search, filters, population="calendar")
    return _task_rows(access, where, params)


def _calendar_data(access, start: date, end: date, search: str, filters: dict) -> dict:
    tasks = _query_calendar_tasks(access, start, end, search, filters)
    # Preserve the legacy rows shape while removing the misleading 25-row cap.
    # Each day is a lightweight index; task details are in the complete rows.
    rows = []
    for task in tasks:
        try:
            due = date.fromisoformat(str(task.get("deadline") or "")[:10])
        except ValueError:
            continue
        if start <= due <= end:
            rows.append(_row(task))
    rows.sort(key=lambda item: (str(item.get("deadline") or "")[:10], str(item.get("id") or "")))
    counts = {}
    for item in rows:
        day = str(item["deadline"])[:10]
        counts[day] = counts.get(day, 0) + 1
    days = []
    cursor = start
    while cursor <= end:
        jy, jm, jd = gregorian_to_jalali(cursor.year, cursor.month, cursor.day)
        iso = cursor.isoformat()
        days.append({
            "date": iso,
            "jalali_date": f"{jy:04d}/{jm:02d}/{jd:02d}",
            "jalali_year": jy,
            "jalali_month": jm,
            "jalali_month_name": JALALI_MONTH_NAMES[jm],
            "jalali_day": jd,
            "gregorian_year": cursor.year,
            "gregorian_month": cursor.month,
            "gregorian_day": cursor.day,
            "weekday": (cursor.weekday() + 2) % 7,
            "count": counts.get(iso, 0),
        })
        cursor += timedelta(days=1)
    return {
        "section": "calendar", "rows": rows, "days": days,
        "total": len(rows), "page": 1, "pages": 1,
        "page_size": len(rows), "pagination_mode": "none",
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "navigation": {
            "jalali": _jalali_month_navigation(start),
            "gregorian": _gregorian_month_navigation(start),
        },
    }


def _query_completed_tasks(access, start: date, end: date, search: str = "", filters: dict | None = None):
    """Completed *in* period, including work created before the period.

    Normalize ISO timestamps into UTC before checking inclusive calendar
    boundaries; the SQL candidate window allows up to +/- 24h offsets.
    """
    where, params = _task_predicate(access, start, end, search, filters, population="completed")
    candidates = _task_rows(access, where, params)
    eligible = []
    for task in candidates:
        completed = _parse_datetime(task.get("completed_at"))
        if completed and start <= completed.astimezone(UTC).date() <= end:
            eligible.append(task)
    return eligible


def _open_deadline_counts(access, today: date, search: str = "", filters: dict | None = None):
    """Count open, authorized, due-date-bearing tasks as of UTC today in SQL."""
    where, params = _task_predicate(
        access, today, today, search, filters, population="open_backlog"
    )
    scope, scope_params = _task_scope(access)
    sql = "SELECT COALESCE(SUM(CASE WHEN substr(deadline,1,10)<? THEN 1 ELSE 0 END),0) AS open_overdue, COALESCE(SUM(CASE WHEN substr(deadline,1,10)>=? THEN 1 ELSE 0 END),0) AS open_on_track FROM tasks WHERE " + scope + " AND (" + where + ")"  # nosec B608 - fixed scoped SQL predicate, bound parameters
    result = sync_query_one(sql, (today.isoformat(), today.isoformat()) + scope_params + params)
    return {
        "open_overdue": int(result["open_overdue"]) if result else 0,
        "open_on_track": int(result["open_on_track"]) if result else 0,
    }


def _count_query_tasks(access, start: date, end: date, search: str = "", filters: dict | None = None):
    """Count earlier-period tasks in SQLite rather than pulling every historical row."""
    where, params = _task_predicate(access, start, end, search, filters)
    # Match exactly the same Core task visibility predicate used for rows.
    scope, scope_params = _task_scope(access)
    sql = "SELECT COUNT(*) AS total FROM tasks WHERE " + scope + " AND (" + where + ")"  # nosec B608 - fixed scoped predicate, parameterized filters
    row = sync_query_one(sql, scope_params + params)
    return int(row["total"]) if row else 0


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
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
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


def _productivity_metrics(tasks, now=None, *, completed_tasks=None, backlog=None) -> dict:
    """Measure created-cohort lead time, completed-cohort punctuality and open backlog.

    With no explicit completed set, preserve the utility's direct-call behavior
    by using the supplied tasks for both cohorts.
    """
    now = now or datetime.now(UTC)
    today_str = now.astimezone(UTC).date().isoformat()
    durations_days = []
    for task in tasks:
        if (task.get("status") or "").lower() not in {"done", "completed"}:
            continue
        created = _parse_datetime(task.get("created_at"))
        completed = _parse_datetime(task.get("completed_at"))
        if created and completed and completed >= created:
            durations_days.append((completed - created).total_seconds() / 86400.0)

    completion_cohort = tasks if completed_tasks is None else completed_tasks
    completed_with_deadline = 0
    completed_on_time = 0
    completed_late = 0
    for task in completion_cohort:
        if (task.get("status") or "").lower() not in {"done", "completed"}:
            continue
        completed = _parse_datetime(task.get("completed_at"))
        deadline_raw = str(task.get("deadline") or "").strip()
        try:
            deadline_day = date.fromisoformat(deadline_raw[:10])
        except (TypeError, ValueError):
            continue
        # A missing/unparseable completion is not evidence of an on-time finish.
        if completed is None:
            continue
        completed_with_deadline += 1
        if completed.astimezone(UTC).date() <= deadline_day:
            completed_on_time += 1
        else:
            completed_late += 1

    if backlog is None:
        open_overdue, open_on_track = 0, 0
        for task in tasks:
            status = (task.get("status") or "").lower()
            if status in {"done", "completed", "cancelled", "canceled"}:
                continue
            deadline_raw = str(task.get("deadline") or "")[:10]
            try:
                deadline_day = date.fromisoformat(deadline_raw)
            except ValueError:
                continue
            if deadline_day.isoformat() < today_str:
                open_overdue += 1
            else:
                open_on_track += 1
    else:
        open_overdue, open_on_track = backlog["open_overdue"], backlog["open_on_track"]

    avg_lead_time_days = round(mean(durations_days), 1) if durations_days else None
    avg_lead_time_hours = round(avg_lead_time_days * 24, 1) if avg_lead_time_days is not None else None
    on_time_rate = round(completed_on_time / completed_with_deadline * 100) if completed_with_deadline else None
    overdue_rate = round(completed_late / completed_with_deadline * 100) if completed_with_deadline else None
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
        "total_with_deadline": sum(bool(task.get("deadline")) for task in tasks),
    }


def _gregorian_month_navigation(start: date) -> dict:
    """Adjacent Gregorian calendar months for the alternate calendar mode."""
    def month_bounds(year, month):
        if month < 1:
            year, month = year - 1, 12
        elif month > 12:
            year, month = year + 1, 1
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        if first < MIN_REPORT_DATE or last > MAX_REPORT_DATE:
            return None
        return {"start": first.isoformat(), "end": last.isoformat()}

    return {
        "calendar": "gregorian",
        "anchor_year": start.year, "anchor_month": start.month,
        "current": month_bounds(start.year, start.month),
        "previous": month_bounds(start.year, start.month - 1),
        "next": month_bounds(start.year, start.month + 1),
    }


def _jalali_month_navigation(start: date) -> dict:
    """Build adjacent Jalali month bounds, independent of Gregorian months."""
    jy, jm, _ = gregorian_to_jalali(start.year, start.month, start.day)

    def month_bounds(year: int, month: int):
        if month < 1:
            year, month = year - 1, 12
        elif month > 12:
            year, month = year + 1, 1
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        first = jdatetime.date(year, month, 1).togregorian()
        last = jdatetime.date(next_year, next_month, 1).togregorian() - timedelta(days=1)
        # The service-level date envelope (#223) also applies to navigation.
        if first < MIN_REPORT_DATE or last > MAX_REPORT_DATE:
            return None
        return {"start": first.isoformat(), "end": last.isoformat()}

    return {
        "calendar": "jalali",
        "anchor_year": jy, "anchor_month": jm,
        "anchor_label": f"{JALALI_MONTH_NAMES[jm]} {jy}",
        "current": month_bounds(jy, jm),
        "previous": month_bounds(jy, jm - 1),
        "next": month_bounds(jy, jm + 1),
    }


def _heatmap_data(tasks, start: date, end: date) -> dict:
    """Build a GitHub-style activity contribution calendar using Jalali dates."""
    created_counts: dict[str, int] = {}
    completed_counts: dict[str, int] = {}
    deadline_counts: dict[str, int] = {}
    titles: dict[str, list[str]] = {}
    
    for task in tasks:
        c_date = str(task.get("created_at") or "")[:10]
        if c_date:
            created_counts[c_date] = created_counts.get(c_date, 0) + 1
            title = str(task.get("title") or "بدون عنوان").strip()
            titles.setdefault(c_date, []).append(title[:70])
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
            "titles": titles.get(iso, [])[:5],
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
        "navigation": _jalali_month_navigation(start),
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
    now = now or datetime.now(UTC)
    return max(0, (now - deadline).total_seconds())


def _priority_rank(task):
    return {"high": 3, "medium": 2, "low": 1}.get(str(task.get("priority") or "medium").lower(), 0)


def _sort_tasks(tasks, sort_key="newest"):
    """Sort the complete filtered task set before pagination."""
    sort_key = sort_key if sort_key in SORT_OPTIONS else "newest"
    now = datetime.now(UTC)
    if sort_key == "newest":
        return sorted(tasks, key=lambda x: (_parse_datetime(x.get("created_at")) or datetime.min.replace(tzinfo=UTC), str(x.get("id") or "")), reverse=True)
    if sort_key == "oldest":
        return sorted(tasks, key=lambda x: (_parse_datetime(x.get("created_at")) or datetime.max.replace(tzinfo=UTC), str(x.get("id") or "")))
    if sort_key == "overdue":
        return sorted(tasks, key=lambda x: (_overdue_seconds(x, now), _parse_datetime(x.get("deadline")) or datetime.max.replace(tzinfo=UTC)), reverse=True)
    if sort_key == "priority":
        return sorted(tasks, key=lambda x: (_priority_rank(x), _parse_datetime(x.get("created_at")) or datetime.min.replace(tzinfo=UTC)), reverse=True)
    return sorted(tasks, key=lambda x: (_duration_seconds(x), _parse_datetime(x.get("created_at")) or datetime.min.replace(tzinfo=UTC)), reverse=True)


def _jalali_date(value: str | None) -> str:
    """Return YYYY/MM/DD in Jalali for an ISO-like Gregorian date value."""
    if not value:
        return ""
    raw = str(value).strip()
    try:
        parsed = date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        return ""
    jy, jm, jd = gregorian_to_jalali(parsed.year, parsed.month, parsed.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def _row(task):
    deadline = task.get("deadline") or ""
    return {
        "id": task.get("id"), "title": task.get("title") or "بدون عنوان",
        "status": task.get("status") or "pending", "status_label": _status(task.get("status")),
        "priority": task.get("priority") or "medium", "priority_label": _priority(task.get("priority")),
        "deadline": deadline, "deadline_jalali": _jalali_date(deadline), "category": task.get("category") or "—",
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
    validated_page = validate_report_page(page)
    query, filters = _decode_filters(search)
    # Without a restrictive structured filter, both populations are identical.
    # This avoids loading the entire reporting interval twice (the UI's sort
    # selection does not change the filter options population).
    tasks = _query_tasks(access, start, end, query, filters)
    constrained = any(str(filters.get(key) or "").strip() for key in (
        "status", "priority", "category", "assignee", "has_deadline", "overdue"
    ))
    base_tasks = _query_tasks(access, start, end, query, {"q": query}) if constrained else tasks
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
    utc_today = datetime.now(UTC).date()
    overdue_snapshot = _open_deadline_counts(access, utc_today, query, filters)
    completed_in_period = _query_completed_tasks(access, start, end, query, filters)
    previous_start, previous_end = _previous_period(start, end)
    # Compare like-for-like datasets: the previous period must use the same
    # search term and structured filters as the current period.
    previous_total = _count_query_tasks(access, previous_start, previous_end, query, filters)
    productivity = _productivity_metrics(tasks, completed_tasks=completed_in_period, backlog=overdue_snapshot)
    result = {
        "report_type": "dashboard",
        "filter": {"period": period, "start": start.isoformat(), "end": end.isoformat(), "search": query, "filters": filters},
        "filter_options": _filter_options(base_tasks),
        "sort_options": [{"value": k, "label": v} for k, v in SORT_OPTIONS.items()],
        "period": {"gregorian": f"{start.isoformat()} تا {end.isoformat()}", "jalali": _jmonth(start)},
        "summary": {
            "total": total, "total_change": _change(total, previous_total), "done": done,
            "in_progress": statuses.get("in_progress", 0), "pending": statuses.get("pending", 0),
            "cancelled": cancelled, "active": total - done - cancelled,
            "overdue": overdue_snapshot["open_overdue"], "backlog_as_of_utc": utc_today.isoformat(),
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
            "completed_in_period": len(completed_in_period),
            "completed_with_deadline": productivity["completed_with_deadline"],
            "productivity": productivity,
        },
        "by_status": [{"key": k, "label": _status(k), "count": v} for k, v in statuses.items()],
        "by_priority": [{"key": k, "label": _priority(k), "count": v} for k, v in priorities.items()],
        "by_category": [{"label": k, "count": v} for k, v in categories.items()],
    }
    if section is None:
        return result
    if section == "calendar":
        # Calendar event dates are deadlines, not creation timestamps.
        # Return every selected-date event; page is deliberately ignored.
        result.update(_calendar_data(access, start, end, query, filters))
        return result
    if section in {"tasks", "deadlines"}:
        selected = [task for task in tasks if section == "tasks" or task.get("deadline")]
        sort_key = str(filters.get("sort") or "newest")
        selected = _sort_tasks(selected, sort_key)
        total_rows = len(selected)
        page = validated_page
        normalized_page_size = int(page_size) if page_size is not None else 25
        if normalized_page_size <= 0:
            # Unpaginated mode is used by exports so CSV/PDF contain the full
            # filtered task set rather than only the first dashboard page.
            visible_tasks = selected
            page = 1
            response_page_size = total_rows
            pages = 1
        else:
            start_index = (page - 1) * normalized_page_size
            visible_tasks = selected[start_index:start_index + normalized_page_size]
            response_page_size = normalized_page_size
            pages = max(1, (total_rows + normalized_page_size - 1) // normalized_page_size)
        visible_rows = [_row(task) for task in visible_tasks]
        result.update({"section": section, "rows": visible_rows, "page": page, "page_size": response_page_size,
                       "total": total_rows, "pages": pages, "sort": sort_key})
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
