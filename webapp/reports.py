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
    return {
        "pending": "شروع‌نشده",
        "in_progress": "در حال انجام",
        "done": "انجام‌شده",
        "cancelled": "لغو شده",
        "canceled": "لغو شده",
    }.get(status or "", status or "نامشخص")


def _priority_label(priority: str) -> str:
    return {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(priority or "", priority or "نامشخص")


def _jalali_month(year: int, month: int) -> str:
    return jdatetime.date.fromgregorian(year=year, month=month, day=1).strftime("%B %Y")


def monthly_report(token: str) -> dict | None:
    access = resolve_report_token(token)
    if not access or access.get("report_type") != "monthly":
        return None

    now = datetime.now(timezone.utc).date()
    start, end = _month_bounds(now.year, now.month)
    tasks = sync_all(
        "tasks",
        "bot_key=? AND user_id=? AND created_at>=? AND created_at<?",
        (access["bot_key"], str(access["user_id"]), start, (date.fromisoformat(end).fromordinal(date.fromisoformat(end).toordinal() + 1)).isoformat()),
    )

    status_counts = Counter((task.get("status") or "pending") for task in tasks)
    priority_counts = Counter((task.get("priority") or "medium") for task in tasks)
    category_counts = Counter((task.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for task in tasks)
    done = status_counts.get("done", 0)
    total = len(tasks)

    return {
        "report_type": "monthly",
        "period": {
            "gregorian": f"{start} تا {end}",
            "jalali": _jalali_month(now.year, now.month),
        },
        "summary": {
            "total": total,
            "done": done,
            "in_progress": status_counts.get("in_progress", 0),
            "pending": status_counts.get("pending", 0),
            "cancelled": status_counts.get("cancelled", status_counts.get("canceled", 0)),
            "completion_rate": round(done / total * 100) if total else 0,
        },
        "by_status": [{"key": key, "label": _status_label(key), "count": count} for key, count in status_counts.most_common()],
        "by_priority": [{"key": key, "label": _priority_label(key), "count": count} for key, count in priority_counts.most_common()],
        "by_category": [{"label": key, "count": count} for key, count in category_counts.most_common()],
        "tasks": [
            {
                "id": task.get("id"),
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "status_label": _status_label(task.get("status", "")),
                "priority": task.get("priority", ""),
                "priority_label": _priority_label(task.get("priority", "")),
                "deadline": task.get("deadline") or "",
                "category": task.get("category") or "",
            }
            for task in sorted(tasks, key=lambda item: item.get("deadline") or "9999-99-99")
        ],
    }
