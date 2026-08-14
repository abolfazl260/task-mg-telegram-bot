"""Web report data access, always scoped by an opaque report token."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timezone

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


def _load_tasks(access: dict) -> tuple[list[dict], str, str]:
    now = datetime.now(timezone.utc).date()
    start, end = _month_bounds(now.year, now.month)
    end_exclusive = (date.fromisoformat(end).toordinal() + 1)
    end_exclusive = date.fromordinal(end_exclusive).isoformat()
    tasks = sync_all("tasks", "bot_key=? AND user_id=? AND created_at>=? AND created_at<?", (access["bot_key"], str(access["user_id"]), start, end_exclusive))
    return tasks, start, end


def monthly_report(token: str, section: str = "summary") -> dict | None:
    access = resolve_report_token(token)
    if not access or access.get("report_type") != "monthly":
        return None

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
        "summary": {
            "total": total, "done": done, "in_progress": status_counts.get("in_progress", 0),
            "pending": status_counts.get("pending", 0), "cancelled": status_counts.get("cancelled", status_counts.get("canceled", 0)),
            "active": active, "overdue": overdue, "with_deadline": with_deadline, "without_deadline": without_deadline,
            "completion_rate": round(done / total * 100) if total else 0,
            "average_completed_per_day": round(done / max(1, (date.today() - date.fromisoformat(start)).days + 1), 2),
        },
        "by_status": [{"key": key, "label": _status_label(key), "count": count} for key, count in status_counts.most_common()],
        "by_priority": [{"key": key, "label": _priority_label(key), "count": count} for key, count in priority_counts.most_common()],
        "by_category": [{"label": key, "count": count} for key, count in category_counts.most_common()],
    }

    if section in {"tasks", "deadlines", "categories", "status", "priority"}:
        if section == "tasks":
            result["rows"] = [{"id": t.get("id"), "title": t.get("title", ""), "status_label": _status_label(t.get("status", "")), "priority_label": _priority_label(t.get("priority", "")), "deadline": t.get("deadline") or "", "category": t.get("category") or ""} for t in sorted(tasks, key=lambda x: x.get("deadline") or "9999-99-99")]
        elif section == "deadlines":
            result["rows"] = [{"title": t.get("title", ""), "deadline": t.get("deadline") or "", "status_label": _status_label(t.get("status", "")), "priority_label": _priority_label(t.get("priority", ""))} for t in sorted(tasks, key=lambda x: x.get("deadline") or "9999-99-99") if t.get("deadline")]
        elif section == "categories":
            result["rows"] = [{"category": k, "count": v} for k, v in category_counts.most_common()]
        elif section == "status":
            result["rows"] = [{"status": _status_label(k), "count": v} for k, v in status_counts.most_common()]
        elif section == "priority":
            result["rows"] = [{"priority": _priority_label(k), "count": v} for k, v in priority_counts.most_common()]
    return result
