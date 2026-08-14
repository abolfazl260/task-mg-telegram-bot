"""Web report data access, scoped by an opaque report token."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timezone

import jdatetime

from services.database import sync_all, sync_scalar, sync_query
from .report_tokens import resolve_report_token


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    first=date(year,month,1); last=date(year,month,calendar.monthrange(year,month)[1])
    return first.isoformat(), last.fromordinal(last.toordinal()+1).isoformat()

def _status_label(status):
    return {"pending":"شروع‌نشده","in_progress":"در حال انجام","done":"انجام‌شده","cancelled":"لغو شده","canceled":"لغو شده"}.get(status or "",status or "نامشخص")

def _priority_label(priority): return {"high":"بالا","medium":"متوسط","low":"پایین"}.get(priority or "",priority or "نامشخص")
def _access(token):
    access=resolve_report_token(token); return access if access and access.get("report_type")=="monthly" else None

def _scope(access):
    now=datetime.now(timezone.utc).date(); start,end=_month_bounds(now.year,now.month)
    return start,end,(access["bot_key"],str(access["user_id"]),start,end)

def _jalali_month(year,month): return jdatetime.date.fromgregorian(year=year,month=month,day=1).strftime("%B %Y")

def monthly_report(token):
    access=_access(token)
    if not access:return None
    start,end,args=_scope(access)
    where="bot_key=? AND user_id=? AND created_at>=? AND created_at<?"
    rows=sync_all("tasks",where,args)
    statuses=Counter((r.get("status") or "pending") for r in rows); priorities=Counter((r.get("priority") or "medium") for r in rows); cats=Counter((r.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for r in rows)
    total=len(rows); done=statuses.get("done",0); today=date.today().isoformat()
    overdue=sum(1 for r in rows if r.get("deadline") and str(r.get("deadline"))<today and (r.get("status") or "pending") not in {"done","cancelled","canceled"})
    with_deadline=sum(1 for r in rows if r.get("deadline"))
    return {"report_type":"monthly","period":{"gregorian":f"{start} تا {date.fromisoformat(end).fromordinal(date.fromisoformat(end).toordinal()-1)}","jalali":_jalali_month(datetime.now(timezone.utc).year,datetime.now(timezone.utc).month)},"summary":{"total":total,"done":done,"in_progress":statuses.get("in_progress",0),"pending":statuses.get("pending",0),"cancelled":statuses.get("cancelled",statuses.get("canceled",0)),"completion_rate":round(done/total*100) if total else 0,"with_deadline":with_deadline,"without_deadline":total-with_deadline,"overdue":overdue},"by_status":[{"key":k,"label":_status_label(k),"count":v} for k,v in statuses.most_common()],"by_priority":[{"key":k,"label":_priority_label(k),"count":v} for k,v in priorities.most_common()],"by_category":[{"label":k,"count":v} for k,v in cats.most_common()],"sections":["tasks","deadlines","status","priority","category"]}

def report_section(token,section,page=1,page_size=25):
    access=_access(token)
    if not access:return None
    if section not in {"tasks","deadlines","status","priority","category"}:return {"error":"invalid_section"}
    page=max(1,int(page)); page_size=min(50,max(1,int(page_size))); offset=(page-1)*page_size
    start,end,args=_scope(access); base="bot_key=? AND user_id=? AND created_at>=? AND created_at<?"; filters=[]
    if section=="deadlines":filters.append("deadline IS NOT NULL AND deadline!=''")
    where=base+(" AND "+" AND ".join(filters) if filters else "")
    if section=="deadlines":order="deadline ASC, id DESC"
    elif section=="status":order="status ASC, id DESC"
    elif section=="priority":order="priority ASC, id DESC"
    elif section=="category":order="category ASC, id DESC"
    else:order="deadline ASC, id DESC"
    total=sync_scalar("SELECT COUNT(*) FROM tasks WHERE "+where,args)
    rows=sync_query("SELECT id,title,status,priority,deadline,category FROM tasks WHERE "+where+f" ORDER BY {order} LIMIT ? OFFSET ?",tuple(args)+(page_size,offset))
    return {"section":section,"page":page,"page_size":page_size,"total":total,"pages":max(1,(total+page_size-1)//page_size),"rows":[{"id":r.get("id"),"title":r.get("title", ""),"status_label":_status_label(r.get("status", "")),"priority_label":_priority_label(r.get("priority", "")),"deadline":r.get("deadline") or "","category":r.get("category") or ""} for r in rows]}
