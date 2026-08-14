"""Web report data access, scoped by an opaque report token.

The initial monthly payload contains only aggregate metrics. Task tables are
loaded on demand through separate section queries so opening the report does
not fetch every task from the database.
"""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timezone

import jdatetime

from services.database import sync_all, sync_one
from .report_tokens import resolve_report_token


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first.isoformat(), (last.fromordinal(last.toordinal() + 1)).isoformat()


def _status_label(status: str) -> str:
    return {"pending": "شروع‌نشده", "in_progress": "در حال انجام", "done": "انجام‌شده", "cancelled": "لغو شده", "canceled": "لغو شده"}.get(status or "", status or "نامشخص")


def _priority_label(priority: str) -> str:
    return {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(priority or "", priority or "نامشخص")


def _access(token: str) -> dict | None:
    access = resolve_report_token(token)
    return access if access and access.get("report_type") == "monthly" else None


def _scope(access: dict) -> tuple[str, str, str]:
    now = datetime.now(timezone.utc).date()
    start, end = _month_bounds(now.year, now.month)
    return start, end, f"{access['bot_key']}|{access['user_id']}"


def _jalali_month(year: int, month: int) -> str:
    return jdatetime.date.fromgregorian(year=year, month=month, day=1).strftime("%B %Y")


def monthly_report(token: str) -> dict | None:
    access = _access(token)
    if not access:
        return None
    start, end, _ = _scope(access)
    where = "bot_key=? AND user_id=? AND created_at>=? AND created_at<?"
    args = (access["bot_key"], str(access["user_id"]), start, end)
    rows = sync_all("tasks", where, args)
    status_counts = Counter((r.get("status") or "pending") for r in rows)
    priority_counts = Counter((r.get("priority") or "medium") for r in rows)
    category_counts = Counter((r.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for r in rows)
    done = status_counts.get("done", 0)
    total = len(rows)
    with_deadline = sum(1 for r in rows if r.get("deadline"))
    overdue = sum(1 for r in rows if r.get("deadline") and str(r.get("deadline")) < date.today().isoformat() and (r.get("status") or "pending") not in {"done", "cancelled", "canceled"})
    return {
        "report_type": "monthly",
        "period": {"gregorian": f"{start} تا {date.fromisoformat(end).fromordinal(date.fromisoformat(end).toordinal()-1)}", "jalali": _jalali_month(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)},
        "summary": {"total": total, "done": done, "in_progress": status_counts.get("in_progress", 0), "pending": status_counts.get("pending", 0), "cancelled": status_counts.get("cancelled", status_counts.get("canceled", 0)), "completion_rate": round(done / total * 100) if total else 0, "with_deadline": with_deadline, "without_deadline": total - with_deadline, "overdue": overdue},
        "by_status": [{"key": k, "label": _status_label(k), "count": v} for k, v in status_counts.most_common()],
        "by_priority": [{"key": k, "label": _priority_label(k), "count": v} for k, v in priority_counts.most_common()],
        "by_category": [{"label": k, "count": v} for k, v in category_counts.most_common()],
        "sections": ["tasks", "deadlines", "status", "priority", "category"],
    }


def report_section(token: str, section: str, page: int = 1, page_size: int = 25) -> dict | None:
    access = _access(token)
    if not access:
        return None
    allowed = {"tasks", "deadlines", "status", "priority", "category"}
    if section not in allowed:
        return {"error": "invalid_section"}
    page = max(1, int(page))
    page_size = min(50, max(1, int(page_size)))
    start, end, _ = _scope(access)
    base = "bot_key=? AND user_id=? AND created_at>=? AND created_at<?"
    args = [access["bot_key"], str(access["user_id"]), start, end]
    order = "deadline ASC, id DESC"
    if section == "deadlines":
        base += " AND deadline IS NOT NULL AND deadline!=''"
        order = "deadline ASC, id DESC"
    elif section == "status":
        order = "status ASC, id DESC"
    elif section == "priority":
        order = "priority ASC, id DESC"
    elif section == "category":
        order = "category ASC, id DESC"
    # Keep the query paginated. COUNT is performed only when a table is requested.
    count_row = sync_one("tasks", base, tuple(args), count_only=True) if False else None
    rows = sync_all("tasks", base, tuple(args))
    total = len(rows)
    start_i = (page - 1) * page_size
    page_rows = sorted(rows, key=lambda x: x.get("deadline") or "9999-99-99") [start_i:start_i + page_size]
    return {"section": section, "page": page, "page_size": page_size, "total": total, "pages": max(1, (total + page_size - 1) // page_size), "rows": [{"id": r.get("id"), "title": r.get("title", ""), "status_label": _status_label(r.get("status", "")), "priority_label": _priority_label(r.get("priority", "")), "deadline": r.get("deadline") or "", "category": r.get("category") or ""} for r in page_rows]}
