"""Web report data access, scoped by an opaque report token.

The dashboard loads aggregates only. Detailed views are loaded on demand.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
import jdatetime

from services.database import sync_scalar, sync_query
from .report_tokens import resolve_report_token


def _month_bounds(year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first.isoformat(), last.fromordinal(last.toordinal() + 1).isoformat()


def _status_label(s):
    return {"pending": "شروع‌نشده", "in_progress": "در حال انجام", "done": "انجام‌شده", "cancelled": "لغو شده", "canceled": "لغو شده"}.get(s or "", s or "نامشخص")


def _priority_label(p):
    return {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(p or "", p or "نامشخص")


def _access(token):
    a = resolve_report_token(token)
    return a if a and a.get("report_type") == "monthly" else None


def _scope(a):
    now = datetime.now(timezone.utc).date()
    start, end = _month_bounds(now.year, now.month)
    return start, end, (a["bot_key"], str(a["user_id"]), start, end)


def _jalali_month(y, m):
    return jdatetime.date.fromgregorian(year=y, month=m, day=1).strftime("%B %Y")


def monthly_report(token):
    """Dashboard payload only; never returns task rows."""
    a = _access(token)
    if not a:
        return None
    start, end, args = _scope(a)
    where = "bot_key=? AND user_id=? AND created_at>=? AND created_at<?"
    total = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where, args)
    done = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status='done'", args)
    in_progress = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status='in_progress'", args)
    pending = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status='pending'", args)
    cancelled = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status IN ('cancelled','canceled')", args)
    with_deadline = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!=''", args)
    overdue = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!='' AND deadline<? AND status NOT IN ('done','cancelled','canceled')", args + (date.today().isoformat(),))
    statuses = sync_query("SELECT COALESCE(NULLIF(status,''),'pending') key,COUNT(*) count FROM tasks WHERE " + where + " GROUP BY key ORDER BY count DESC", args)
    priorities = sync_query("SELECT COALESCE(NULLIF(priority,''),'medium') key,COUNT(*) count FROM tasks WHERE " + where + " GROUP BY key ORDER BY count DESC", args)
    cats = sync_query("SELECT COALESCE(NULLIF(TRIM(category),''),'بدون دسته‌بندی') label,COUNT(*) count FROM tasks WHERE " + where + " GROUP BY label ORDER BY count DESC", args)
    return {
        "report_type": "web",
        "period": {"gregorian": f"{start} تا {date.fromisoformat(end).fromordinal(date.fromisoformat(end).toordinal()-1)}", "jalali": _jalali_month(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)},
        "summary": {"total": total, "done": done, "in_progress": in_progress, "pending": pending, "cancelled": cancelled, "completion_rate": round(done / total * 100) if total else 0, "with_deadline": with_deadline, "without_deadline": total - with_deadline, "overdue": overdue},
        "by_status": [{"key": r["key"], "label": _status_label(r["key"]), "count": r["count"]} for r in statuses],
        "by_priority": [{"key": r["key"], "label": _priority_label(r["key"]), "count": r["count"]} for r in priorities],
        "by_category": [{"label": r["label"], "count": r["count"]} for r in cats],
        "sections": ["tasks", "kanban", "calendar", "deadlines", "status", "priority", "category"],
    }


def report_section(token, section, page=1, page_size=25):
    a = _access(token)
    if not a:
        return None
    allowed = {"tasks", "kanban", "calendar", "deadlines", "status", "priority", "category"}
    if section not in allowed:
        return {"error": "invalid_section"}
    page = max(1, int(page))
    page_size = min(50, max(1, int(page_size)))
    start, end, args = _scope(a)
    where = "bot_key=? AND user_id=? AND created_at>=? AND created_at<?"
    if section == "deadlines":
        where += " AND deadline IS NOT NULL AND deadline!=''"
    if section == "calendar":
        # Calendar is intentionally loaded only after the user clicks it.
        rows = sync_query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!='' ORDER BY deadline ASC,id DESC LIMIT 200", args)
        return {"section": section, "rows": [{"id": r.get("id"), "title": r.get("title", ""), "status": r.get("status", ""), "status_label": _status_label(r.get("status", "")), "priority_label": _priority_label(r.get("priority", "")), "deadline": r.get("deadline") or "", "category": r.get("category") or ""} for r in rows]}
    if section == "kanban":
        # Kanban is also lazy-loaded. Limit each board to 50 cards.
        rows = sync_query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + " ORDER BY id DESC LIMIT 200", args)
        columns = {"pending": [], "in_progress": [], "done": [], "cancelled": []}
        for r in rows:
            key = r.get("status") or "pending"
            if key in ("canceled", "cancelled"):
                key = "cancelled"
            columns.setdefault(key, []).append({"id": r.get("id"), "title": r.get("title", ""), "status_label": _status_label(r.get("status", "")), "priority_label": _priority_label(r.get("priority", "")), "deadline": r.get("deadline") or "", "category": r.get("category") or ""})
        for key in columns:
            columns[key] = columns[key][:50]
        return {"section": section, "columns": columns, "limited": len(rows) >= 200}
    offset = (page - 1) * page_size
    order = {"deadlines": "deadline ASC,id DESC", "status": "status ASC,id DESC", "priority": "priority ASC,id DESC", "category": "category ASC,id DESC", "tasks": "deadline ASC,id DESC"}[section]
    total = sync_scalar("SELECT COUNT(*) FROM tasks WHERE " + where, args)
    rows = sync_query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + f" ORDER BY {order} LIMIT ? OFFSET ?", tuple(args) + (page_size, offset))
    return {"section": section, "page": page, "page_size": page_size, "total": total, "pages": max(1, (total + page_size - 1) // page_size), "rows": [{"id": r.get("id"), "title": r.get("title", ""), "status_label": _status_label(r.get("status", "")), "priority_label": _priority_label(r.get("priority", "")), "deadline": r.get("deadline") or "", "category": r.get("category") or ""} for r in rows]}
