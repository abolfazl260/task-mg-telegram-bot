"""Web report data access, always scoped by an opaque report token."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import jdatetime

from services.database import sync_all
from .report_tokens import resolve_report_token


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first.isoformat(), last.isoformat()


def _status_label(status: str) -> str:
    return {"pending": "شروع‌نشده", "in_progress": "در حال انجام", "done": "انجام‌شده", "cancelled": "لغو شده", "canceled": "لغو شده"}.get(status or "", status or "نامشخص")


def _priority_label(priority: str) -> str:
    return {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(priority or "", priority or "نامشخص")


def _jalali_month(year: int, month: int) -> str:
    return jdatetime.date.fromgregorian(year=year, month=month, day=1).strftime("%B %Y")


def _jalali_day(value: date) -> str:
    return jdatetime.date.fromgregorian(year=value.year, month=value.month, day=value.day).strftime("%-d %B %Y")


def _load_tasks(access: dict) -> tuple[list[dict], str, str]:
    now = datetime.now(timezone.utc).date()
    start, end = _month_bounds(now.year, now.month)
    end_exclusive = date.fromordinal(date.fromisoformat(end).toordinal() + 1).isoformat()
    tasks = sync_all("tasks", "bot_key=? AND user_id=? AND created_at>=? AND created_at<?", (access["bot_key"], str(access["user_id"]), start, end_exclusive))
    return tasks, start, end


def _week_report(access: dict) -> dict:
    """Return the next seven calendar days grouped by task deadline.

    This is deliberately a lazy section: it is only called when the weekly
    schedule is requested. Tasks are grouped by their *deadline*, not by
    creation time. The assignee stored on each task is included in every row.
    """
    today = datetime.now(timezone.utc).date()
    week_end = today + timedelta(days=6)
    start = today.isoformat()
    end_exclusive = (week_end + timedelta(days=1)).isoformat()
    tasks = sync_all(
        "tasks",
        "bot_key=? AND user_id=? AND deadline>=? AND deadline<?",
        (access["bot_key"], str(access["user_id"]), start, end_exclusive),
    )

    buckets = []
    day_names = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    for offset in range(7):
        current = today + timedelta(days=offset)
        rows = []
        for task in tasks:
            raw_deadline = str(task.get("deadline") or "")
            if not raw_deadline[:10] == current.isoformat():
                continue
            rows.append({
                "id": task.get("id"),
                "title": task.get("title") or "بدون عنوان",
                "priority": task.get("priority") or "medium",
                "priority_label": _priority_label(task.get("priority") or "medium"),
                "status": task.get("status") or "pending",
                "status_label": _status_label(task.get("status") or "pending"),
                "deadline": raw_deadline,
                "category": task.get("category") or "—",
                "assignee": task.get("assignee_name") or task.get("assignee_username") or "بدون مسئول",
            })
        rows.sort(key=lambda x: (x["deadline"], x["title"]))
        buckets.append({
            "offset": offset,
            "date": current.isoformat(),
            "jalali": _jalali_day(current),
            "weekday": day_names[current.weekday() % 7],
            "label": "برنامه امروز" if offset == 0 else ("برنامه فردا" if offset == 1 else f"برنامه {day_names[current.weekday() % 7]}"),
            "rows": rows,
            "count": len(rows),
        })
    return {"start": start, "end": week_end.isoformat(), "days": buckets, "total": len(tasks)}


def _habit_report(access: dict, start: str, end: str) -> dict:
    """Build habit statistics only when the user explicitly requests this section."""
    uid = str(access["user_id"])
    habits = sync_all("habits", "user_id=?", (uid,))
    logs = sync_all("habit_logs", "user_id=? AND done_date>=? AND done_date<=?", (uid, start, end))
    log_by_habit = Counter(str(x.get("habit_id")) for x in logs)
    active = [h for h in habits if h.get("active") in (1, True, "1")]
    rows = []
    total_completed = 0
    for habit in active:
        hid = str(habit.get("id"))
        completed = log_by_habit.get(hid, 0)
        total_completed += completed
        rows.append({
            "id": hid,
            "title": habit.get("title") or "بدون عنوان",
            "category": habit.get("category") or "بدون دسته‌بندی",
            "target": habit.get("target") or "—",
            "repeat_type": {"daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه"}.get(habit.get("repeat_type"), habit.get("repeat_type") or "—"),
            "completed": completed,
            "last_done": max((x.get("done_date") for x in logs if str(x.get("habit_id")) == hid and x.get("done_date")), default="—"),
        })
    rows.sort(key=lambda x: (-x["completed"], x["title"]))
    by_category = Counter(x["category"] for x in rows)
    by_day = Counter(x.get("done_date") for x in logs if x.get("done_date"))
    return {
        "total_habits": len(habits), "active_habits": len(active), "completed_logs": total_completed,
        "completion_days": len(by_day), "rows": rows,
        "by_category": [{"label": k, "count": v} for k, v in by_category.most_common()],
        "daily_activity": [{"date": k, "count": v} for k, v in sorted(by_day.items())],
    }


def monthly_report(token: str, section: str = "summary") -> dict | None:
    access = resolve_report_token(token)
    if not access or access.get("report_type") != "monthly":
        return None

    # Keep the weekly schedule lazy: do not load it while rendering the summary.
    if section == "week":
        return {"report_type": "weekly_schedule", "week": _week_report(access)}

    tasks, start, end = _load_tasks(access)
    status_counts = Counter((task.get("status") or "pending") for task in tasks)
    priority_counts = Counter((task.get("priority") or "medium") for task in tasks)
    category_counts = Counter((task.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for task in tasks)
    done = status_counts.get("done", 0)
    total = len(tasks)
    overdue = sum(1 for task in tasks if task.get("deadline") and task.get("deadline") < date.today().isoformat() and task.get("status") not in {"done", "cancelled", "canceled"})
    with_deadline = sum(1 for task in tasks if task.get("deadline"))
    without_deadline = total - with_deadline
    active = total - done - status_counts.get("cancelled", status_counts.get("canceled", 0))

    result = {
        "report_type": "monthly",
        "period": {"gregorian": f"{start} تا {end}", "jalali": _jalali_month(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)},
        "summary": {"total": total, "done": done, "in_progress": status_counts.get("in_progress", 0), "pending": status_counts.get("pending", 0), "cancelled": status_counts.get("cancelled", status_counts.get("canceled", 0)), "active": active, "overdue": overdue, "with_deadline": with_deadline, "without_deadline": without_deadline, "completion_rate": round(done / total * 100) if total else 0, "average_completed_per_day": round(done / max(1, (date.today() - date.fromisoformat(start)).days + 1), 2)},
        "by_status": [{"key": k, "label": _status_label(k), "count": v} for k, v in status_counts.most_common()],
        "by_priority": [{"key": k, "label": _priority_label(k), "count": v} for k, v in priority_counts.most_common()],
        "by_category": [{"label": k, "count": v} for k, v in category_counts.most_common()],
    }

    if section == "habits":
        result["habits"] = _habit_report(access, start, end)
        return result

    if section in {"tasks", "deadlines", "categories", "status", "priority"}:
        if section == "tasks":
            result["rows"] = [{"id": t.get("id"), "title": t.get("title", ""), "status_label": _status_label(t.get("status", "")), "priority_label": _priority_label(t.get("priority", "")), "deadline": t.get("deadline") or "", "category": t.get("category") or "", "assignee": t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"} for t in sorted(tasks, key=lambda x: x.get("deadline") or "9999-99-99")]
        elif section == "deadlines":
            result["rows"] = [{"title": t.get("title", ""), "deadline": t.get("deadline") or "", "status_label": _status_label(t.get("status", "")), "priority_label": _priority_label(t.get("priority", "")), "assignee": t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"} for t in sorted(tasks, key=lambda x: x.get("deadline") or "9999-99-99") if t.get("deadline")]
        elif section == "categories":
            result["rows"] = [{"category": k, "count": v} for k, v in category_counts.most_common()]
        elif section == "status":
            result["rows"] = [{"status": _status_label(k), "count": v} for k, v in status_counts.most_common()]
        elif section == "priority":
            result["rows"] = [{"priority": _priority_label(k), "count": v} for k, v in priority_counts.most_common()]
    return result
