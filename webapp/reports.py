"""Web report data access, scoped by an opaque report token.

The web report is an all-tasks dashboard, not a monthly report. The initial
payload contains only aggregates; detailed tables/kanban/calendar data are
loaded only when the user selects a section.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from services.database import DB_PATH
from .report_tokens import resolve_report_token


def _status_label(s):
    return {"pending": "شروع‌نشده", "in_progress": "در حال انجام", "done": "انجام‌شده", "cancelled": "لغو شده", "canceled": "لغو شده"}.get(s or "", s or "نامشخص")


def _priority_label(p):
    return {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(p or "", p or "نامشخص")


def _access(token):
    a = resolve_report_token(token)
    return a if a and a.get("report_type") == "monthly" else None


def _scope(a):
    return "bot_key=? AND user_id=?", (str(a["bot_key"]), str(a["user_id"]))


def _query(sql, params=(), *, scalar=False):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.execute(sql, tuple(params))
        if scalar:
            row = cur.fetchone()
            return row[0] if row else 0
        return [dict(row) for row in cur.fetchall()]


def monthly_report(token):
    """Return the lightweight dashboard summary for all tasks of the user."""
    a = _access(token)
    if not a:
        return None
    where, args = _scope(a)
    total = _query("SELECT COUNT(*) FROM tasks WHERE " + where, args, scalar=True)
    done = _query("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status='done'", args, scalar=True)
    in_progress = _query("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status='in_progress'", args, scalar=True)
    pending = _query("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status='pending'", args, scalar=True)
    cancelled = _query("SELECT COUNT(*) FROM tasks WHERE " + where + " AND status IN ('cancelled','canceled')", args, scalar=True)
    with_deadline = _query("SELECT COUNT(*) FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!=''", args, scalar=True)
    overdue = _query("SELECT COUNT(*) FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!='' AND substr(deadline,1,10)<? AND status NOT IN ('done','cancelled','canceled')", args + (date.today().isoformat(),), scalar=True)
    statuses = _query("SELECT COALESCE(NULLIF(status,''),'pending') key,COUNT(*) count FROM tasks WHERE " + where + " GROUP BY key ORDER BY count DESC", args)
    priorities = _query("SELECT COALESCE(NULLIF(priority,''),'medium') key,COUNT(*) count FROM tasks WHERE " + where + " GROUP BY key ORDER BY count DESC", args)
    cats = _query("SELECT COALESCE(NULLIF(TRIM(category),''),'بدون دسته‌بندی') label,COUNT(*) count FROM tasks WHERE " + where + " GROUP BY label ORDER BY count DESC", args)
    return {
        "report_type": "web",
        "period": {"label": "همه وظایف", "gregorian": "از ابتدای ثبت اطلاعات تا امروز"},
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
    where, args = _scope(a)
    if section == "deadlines":
        where += " AND deadline IS NOT NULL AND deadline!=''"
    if section == "calendar":
        rows = _query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!='' ORDER BY deadline ASC,id DESC LIMIT 200", args)
        return {"section": section, "rows": [{"id": r.get("id"), "title": r.get("title", ""), "status": r.get("status", ""), "status_label": _status_label(r.get("status", "")), "priority_label": _priority_label(r.get("priority", "")), "deadline": r.get("deadline") or "", "category": r.get("category") or ""} for r in rows]}
    if section == "kanban":
        rows = _query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + " ORDER BY id DESC LIMIT 200", args)
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
    order = {"deadlines": "deadline ASC,id DESC", "status": "status ASC,id DESC", "priority": "priority ASC,id DESC", "category": "category ASC,id DESC", "tasks": "created_at DESC,id DESC"}[section]
    total = _query("SELECT COUNT(*) FROM tasks WHERE " + where, args, scalar=True)
    rows = _query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + f" ORDER BY {order} LIMIT ? OFFSET ?", tuple(args) + (page_size, offset))
    return {"section": section, "page": page, "page_size": page_size, "total": total, "pages": max(1, (total + page_size - 1) // page_size), "rows": [{"id": r.get("id"), "title": r.get("title", ""), "status_label": _status_label(r.get("status", "")), "priority_label": _priority_label(r.get("priority", "")), "deadline": r.get("deadline") or "", "category": r.get("category") or ""} for r in rows]}
