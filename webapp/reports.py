"""Web report data access, scoped by an opaque report token."""
from __future__ import annotations

import calendar
import json
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
        "sections": ["tasks", "kanban", "calendar", "deadlines", "status", "priority", "category", "heatmap", "recent_changes"],
    }


def _heatmap(token, a):
    where, args = _scope(a)
    today = date.today()
    year, month = today.year, today.month
    month_start = date(year, month, 1).isoformat()
    next_year = year + (1 if month == 12 else 0)
    next_month = 1 if month == 12 else month + 1
    month_end = date(next_year, next_month, 1).isoformat()
    rows = _query("SELECT substr(created_at,1,10) day, COUNT(*) count FROM tasks WHERE " + where + " AND substr(created_at,1,10)>=? AND substr(created_at,1,10)<? GROUP BY day ORDER BY day", args + (month_start, month_end))
    counts = {r["day"]: int(r["count"]) for r in rows if r.get("day")}
    days = calendar.monthrange(year, month)[1]
    values = [{"day": d, "date": f"{year:04d}-{month:02d}-{d:02d}", "count": counts.get(f"{year:04d}-{month:02d}-{d:02d}", 0)} for d in range(1, days + 1)]
    maximum = max((v["count"] for v in values), default=0)
    return {"section": "heatmap", "year": year, "month": month, "month_label": f"{year:04d}/{month:02d}", "days": values, "max_count": maximum, "total": sum(v["count"] for v in values)}


def _recent_changes(token, a, limit=100):
    """Return recent activity from existing comment and assignment history tables.

    This is deliberately read-only and lazy-loaded. Status changes are shown when
    they have been recorded as activity by the task workflow; older rows without
    an audit event are not fabricated.
    """
    where, args = _scope(a)
    task_filter = "t.bot_key=? AND t.user_id=?"
    comments = _query(
        "SELECT c.id,c.task_id,c.author_id,c.author_name,c.author_username,c.content_json,c.created_at,t.title "
        "FROM task_comments c JOIN tasks t ON t.id=c.task_id "
        "WHERE " + task_filter + " ORDER BY c.created_at DESC,c.id DESC LIMIT ?",
        args + (limit,),
    )
    assignments = _query(
        "SELECT h.id,h.task_id,h.actor_id,h.action,h.old_assignee_name,h.new_assignee_name,h.created_at,t.title "
        "FROM task_assignment_history h JOIN tasks t ON t.id=h.task_id "
        "WHERE " + task_filter + " ORDER BY h.created_at DESC,h.id DESC LIMIT ?",
        args + (limit,),
    )
    events = []
    for r in comments:
        try: content = json.loads(r.get("content_json") or "{}")
        except Exception: content = {}
        if not isinstance(content, dict): content = {"content": content}
        ctype = content.get("type") or "text"
        text = content.get("text") or content.get("caption") or content.get("file_name") or content.get("emoji") or "محتوا ارسال شد"
        labels = {"text":"کامنت ثبت کرد", "photo":"تصویر ارسال کرد", "voice":"پیام صوتی ارسال کرد", "audio":"فایل صوتی ارسال کرد", "document":"فایل ارسال کرد", "video":"ویدئو ارسال کرد", "animation":"گیف ارسال کرد", "sticker":"استیکر ارسال کرد", "contact":"مخاطب ارسال کرد", "location":"موقعیت ارسال کرد"}
        events.append({"id": f"comment-{r['id']}", "kind":"comment", "icon":"💬", "title":labels.get(ctype,"کامنت ثبت کرد"), "task_id":r.get("task_id"), "task_title":r.get("title") or "بدون عنوان", "actor":r.get("author_name") or "کاربر", "actor_username":r.get("author_username") or "", "text":str(text).replace("\n"," ")[:220], "created_at":r.get("created_at") or ""})
    for r in assignments:
        action = r.get("action") or "assigned"
        if action in ("unassigned", "removed"):
            title = "مسئولیت تسک را حذف کرد"
            text = f"مسئول قبلی: {r.get('old_assignee_name') or '—'}"
        elif action in ("claimed", "self_assigned"):
            title = "تسک را برای خود برداشت"
            text = f"مسئول: {r.get('new_assignee_name') or '—'}"
        else:
            title = "مسئول تسک را تغییر داد"
            text = f"{r.get('old_assignee_name') or 'بدون مسئول'} ← {r.get('new_assignee_name') or 'بدون مسئول'}"
        events.append({"id": f"assignment-{r['id']}", "kind":"assignment", "icon":"👤", "title":title, "task_id":r.get("task_id"), "task_title":r.get("title") or "بدون عنوان", "actor":r.get("actor_id") or "کاربر", "actor_username":"", "text":text, "created_at":r.get("created_at") or ""})
    events.sort(key=lambda x: (x.get("created_at") or "", x.get("id") or ""), reverse=True)
    return {"section":"recent_changes", "total":len(events), "events":events[:limit]}


def report_section(token, section, page=1, page_size=25):
    a = _access(token)
    if not a:
        return None
    allowed = {"tasks", "kanban", "calendar", "deadlines", "status", "priority", "category", "heatmap", "recent_changes"}
    if section not in allowed:
        return {"error": "invalid_section"}
    if section == "heatmap": return _heatmap(token, a)
    if section == "recent_changes": return _recent_changes(token, a)
    page = max(1, int(page)); page_size = min(50, max(1, int(page_size)))
    where, args = _scope(a)
    if section == "deadlines": where += " AND deadline IS NOT NULL AND deadline!=''"
    if section == "calendar":
        rows = _query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + " AND deadline IS NOT NULL AND deadline!='' ORDER BY deadline ASC,id DESC LIMIT 200", args)
        return {"section": section, "rows": [{"id":r.get("id"),"title":r.get("title", ""),"status":r.get("status", ""),"status_label":_status_label(r.get("status", "")),"priority":r.get("priority", ""),"priority_label":_priority_label(r.get("priority", "")),"deadline":r.get("deadline") or "","category":r.get("category") or ""} for r in rows]}
    if section == "kanban":
        rows = _query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + " ORDER BY id DESC LIMIT 200", args)
        columns={"pending":[],"in_progress":[],"done":[],"cancelled":[]}
        for r in rows:
            key=r.get("status") or "pending"
            if key in ("canceled","cancelled"): key="cancelled"
            columns.setdefault(key,[]).append({"id":r.get("id"),"title":r.get("title", ""),"status_label":_status_label(r.get("status", "")),"priority_label":_priority_label(r.get("priority", "")),"priority":r.get("priority", ""),"deadline":r.get("deadline") or "","category":r.get("category") or ""})
        for key in columns: columns[key]=columns[key][:50]
        return {"section":section,"columns":columns,"limited":len(rows)>=200,"total":sum(len(v) for v in columns.values())}
    offset=(page-1)*page_size
    order={"deadlines":"deadline ASC,id DESC","status":"status ASC,id DESC","priority":"priority ASC,id DESC","category":"category ASC,id DESC","tasks":"created_at DESC,id DESC"}[section]
    total=_query("SELECT COUNT(*) FROM tasks WHERE " + where,args,scalar=True)
    rows=_query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE " + where + f" ORDER BY {order} LIMIT ? OFFSET ?",tuple(args)+(page_size,offset))
    return {"section":section,"page":page,"page_size":page_size,"total":total,"pages":max(1,(total+page_size-1)//page_size),"rows":[{"id":r.get("id"),"title":r.get("title", ""),"status_label":_status_label(r.get("status", "")),"priority":r.get("priority", ""),"priority_label":_priority_label(r.get("priority", "")),"deadline":r.get("deadline") or "","category":r.get("category") or ""} for r in rows]}
