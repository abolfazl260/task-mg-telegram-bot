"""Web report data access, always scoped by an opaque report token."""
from __future__ import annotations

import calendar
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import jdatetime

from services.database import sync_all
from .report_tokens import resolve_report_token


def _status_label(v):
    return {"pending":"شروع‌نشده","in_progress":"در حال انجام","done":"انجام‌شده","cancelled":"لغو شده","canceled":"لغو شده"}.get(v or "",v or "نامشخص")

def _priority_label(v):
    return {"high":"بالا","medium":"متوسط","low":"پایین"}.get(v or "",v or "نامشخص")

def _access(token):
    a=resolve_report_token(token)
    return a if a and a.get("report_type")=="monthly" else None

def _month_bounds():
    now=datetime.now(timezone.utc).date(); start=date(now.year,now.month,1); end=date(now.year,now.month,calendar.monthrange(now.year,now.month)[1]); return start,end

def _jalali_day(v):
    return jdatetime.date.fromgregorian(year=v.year,month=v.month,day=v.day).strftime("%-d %B %Y")

def _jalali_month(v):
    return jdatetime.date.fromgregorian(year=v.year,month=v.month,day=1).strftime("%B %Y")

def _tasks(a,start=None,end=None):
    cond="bot_key=? AND user_id=?"; args=[a["bot_key"],str(a["user_id"])]
    if start is not None: cond+=" AND created_at>=?"; args.append(start.isoformat() if isinstance(start,date) else start)
    if end is not None: cond+=" AND created_at<?"; args.append(end.isoformat() if isinstance(end,date) else end)
    return sync_all("tasks",cond,tuple(args))

def _week_report(a):
    today=datetime.now(timezone.utc).date(); end=today+timedelta(days=6)
    tasks=sync_all("tasks","bot_key=? AND user_id=? AND deadline>=? AND deadline<?",(a["bot_key"],str(a["user_id"]),today.isoformat(),(end+timedelta(days=1)).isoformat()))
    names=["شنبه","یکشنبه","دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه"]
    days=[]
    for i in range(7):
        d=today+timedelta(days=i); rows=[]
        for t in tasks:
            raw=str(t.get("deadline") or "")
            if raw[:10]!=d.isoformat(): continue
            rows.append({"id":t.get("id"),"title":t.get("title") or "بدون عنوان","priority":t.get("priority") or "medium","priority_label":_priority_label(t.get("priority") or "medium"),"status":t.get("status") or "pending","status_label":_status_label(t.get("status") or "pending"),"deadline":raw,"category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"})
        rows.sort(key=lambda x:(x["deadline"],x["title"]))
        days.append({"offset":i,"date":d.isoformat(),"jalali":_jalali_day(d),"weekday":names[d.weekday()],"label":"برنامه امروز" if i==0 else ("برنامه فردا" if i==1 else f"برنامه {names[d.weekday()]}"),"rows":rows,"count":len(rows)})
    return {"start":today.isoformat(),"end":end.isoformat(),"days":days,"total":len(tasks)}

def _habit_report(a,start,end):
    uid=str(a["user_id"]); habits=sync_all("habits","user_id=?",(uid,)); logs=sync_all("habit_logs","user_id=? AND done_date>=? AND done_date<=?",(uid,start.isoformat(),end.isoformat()))
    counts=Counter(str(x.get("habit_id")) for x in logs); active=[h for h in habits if h.get("active") in (1,True,"1")]; rows=[]
    for h in active:
        hid=str(h.get("id")); completed=counts.get(hid,0); relevant=[x.get("done_date") for x in logs if str(x.get("habit_id"))==hid and x.get("done_date")]
        rows.append({"id":hid,"title":h.get("title") or "بدون عنوان","category":h.get("category") or "بدون دسته‌بندی","target":h.get("target") or "—","repeat_type":{"daily":"روزانه","weekly":"هفتگی","monthly":"ماهانه"}.get(h.get("repeat_type"),h.get("repeat_type") or "—"),"completed":completed,"last_done":max(relevant,default="—")})
    rows.sort(key=lambda x:(-x["completed"],x["title"])); bycat=Counter(x["category"] for x in rows); byday=Counter(x.get("done_date") for x in logs if x.get("done_date"))
    return {"total_habits":len(habits),"active_habits":len(active),"completed_logs":sum(counts.values()),"completion_days":len(byday),"rows":rows,"by_category":[{"label":k,"count":v} for k,v in bycat.most_common()],"daily_activity":[{"date":k,"count":v} for k,v in sorted(byday.items())]}

def _heatmap(a):
    today=datetime.now(timezone.utc).date(); start=date(today.year,today.month,1); nextm=date(today.year+(today.month==12),1 if today.month==12 else today.month+1,1)
    tasks=sync_all("tasks","bot_key=? AND user_id=? AND deadline>=? AND deadline<? AND deadline IS NOT NULL AND deadline!=''",(a["bot_key"],str(a["user_id"]),start.isoformat(),nextm.isoformat()))
    counts=Counter(str(t.get("deadline"))[:10] for t in tasks if t.get("deadline")); values=[{"day":d,"date":f"{today.year:04d}-{today.month:02d}-{d:02d}","count":counts.get(f"{today.year:04d}-{today.month:02d}-{d:02d}",0)} for d in range(1,calendar.monthrange(today.year,today.month)[1]+1)]; maximum=max((x["count"] for x in values),default=0)
    return {"section":"heatmap","year":today.year,"month":today.month,"month_label":f"{today.year:04d}/{today.month:02d} · {_jalali_month(today)}","days":values,"max_count":maximum,"total":sum(x["count"] for x in values)}

def _recent_changes(a,limit=100):
    args=(a["bot_key"],str(a["user_id"])); events=[]
    try:
        comments=sync_all("task_comments","c.id IS NOT NULL AND t.bot_key=? AND t.user_id=?",args,join="JOIN tasks t ON t.id=c.task_id",columns="c.id,c.task_id,c.author_id,c.author_name,c.author_username,c.content_json,c.created_at,t.title",alias="c")
    except Exception: comments=[]
    try:
        assignments=sync_all("task_assignment_history","h.id IS NOT NULL AND t.bot_key=? AND t.user_id=?",args,join="JOIN tasks t ON t.id=h.task_id",columns="h.id,h.task_id,h.actor_id,h.action,h.old_assignee_name,h.new_assignee_name,h.created_at,t.title",alias="h")
    except Exception: assignments=[]
    for r in comments:
        try: c=json.loads(r.get("content_json") or "{}")
        except Exception: c={}
        if not isinstance(c,dict): c={"content":c}
        typ=c.get("type") or "text"; labels={"text":"کامنت ثبت کرد","photo":"تصویر ارسال کرد","voice":"پیام صوتی ارسال کرد","audio":"فایل صوتی ارسال کرد","document":"فایل ارسال کرد","video":"ویدئو ارسال کرد","animation":"گیف ارسال کرد","sticker":"استیکر ارسال کرد"}; text=c.get("text") or c.get("caption") or c.get("file_name") or "محتوا ارسال شد"
        events.append({"id":f"comment-{r.get('id')}","kind":"comment","icon":"💬","title":labels.get(typ,"کامنت ثبت کرد"),"task_id":r.get("task_id"),"task_title":r.get("title") or "بدون عنوان","actor":r.get("author_name") or "کاربر","actor_username":r.get("author_username") or "","text":str(text).replace("\n"," ")[:220],"created_at":r.get("created_at") or ""})
    for r in assignments:
        action=r.get("action") or "assigned"
        if action in ("unassigned","removed"): title="مسئولیت تسک را حذف کرد"; text=f"مسئول قبلی: {r.get('old_assignee_name') or '—'}"
        elif action in ("claimed","self_assigned"): title="تسک را برای خود برداشت"; text=f"مسئول: {r.get('new_assignee_name') or '—'}"
        else: title="مسئول تسک را تغییر داد"; text=f"{r.get('old_assignee_name') or 'بدون مسئول'} ← {r.get('new_assignee_name') or 'بدون مسئول'}"
        events.append({"id":f"assignment-{r.get('id')}","kind":"assignment","icon":"👤","title":title,"task_id":r.get("task_id"),"task_title":r.get("title") or "بدون عنوان","actor":r.get("actor_id") or "کاربر","actor_username":"","text":text,"created_at":r.get("created_at") or ""})
    events.sort(key=lambda x:(x.get("created_at") or "",x.get("id") or ""),reverse=True); return {"section":"recent_changes","total":len(events),"events":events[:limit]}

def monthly_report(token,section="summary"):
    a=_access(token)
    if not a:return None
    if section=="week":return {"report_type":"weekly_schedule","week":_week_report(a)}
    now=datetime.now(timezone.utc).date(); start,end=_month_bounds(); end_ex=end+timedelta(days=1); tasks=_tasks(a,start,end_ex)
    statuses=Counter((t.get("status") or "pending") for t in tasks); priorities=Counter((t.get("priority") or "medium") for t in tasks); cats=Counter((t.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for t in tasks); total=len(tasks); done=statuses.get("done",0); cancelled=statuses.get("cancelled",statuses.get("canceled",0)); deadlines=[t for t in tasks if t.get("deadline")]; overdue=sum(1 for t in deadlines if str(t.get("deadline"))[:10]<now.isoformat() and t.get("status") not in {"done","cancelled","canceled"})
    result={"report_type":"monthly","period":{"gregorian":f"{start.isoformat()} تا {end.isoformat()}","jalali":_jalali_month(now)},"summary":{"total":total,"done":done,"in_progress":statuses.get("in_progress",0),"pending":statuses.get("pending",0),"cancelled":cancelled,"active":total-done-cancelled,"overdue":overdue,"with_deadline":len(deadlines),"without_deadline":total-len(deadlines),"completion_rate":round(done/total*100) if total else 0},"by_status":[{"key":k,"label":_status_label(k),"count":v} for k,v in statuses.most_common()],"by_priority":[{"key":k,"label":_priority_label(k),"count":v} for k,v in priorities.most_common()],"by_category":[{"label":k,"count":v} for k,v in cats.most_common()]}
    if section=="heatmap":return _heatmap(a)
    if section=="recent_changes":return _recent_changes(a)
    if section=="habits":result["habits"]=_habit_report(a,start,end); return result
    if section=="kanban":
        columns={"pending":[],"in_progress":[],"done":[],"cancelled":[]}
        for t in sorted(tasks,key=lambda x:x.get("id") or 0,reverse=True):
            k=t.get("status") or "pending"; k="cancelled" if k in {"canceled","cancelled"} else k; columns.setdefault(k,[]).append({"id":t.get("id"),"title":t.get("title") or "بدون عنوان","status_label":_status_label(t.get("status")),"priority":t.get("priority") or "medium","priority_label":_priority_label(t.get("priority")),"deadline":t.get("deadline") or "","category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"})
        return {"section":"kanban","columns":columns,"total":sum(len(v) for v in columns.values())}
    if section in {"tasks","deadlines"}:
        selected=[t for t in tasks if section=="tasks" or t.get("deadline")]; selected.sort(key=lambda x:x.get("deadline") or "9999-99-99"); result["rows"]= [{"id":t.get("id"),"title":t.get("title") or "بدون عنوان","status":t.get("status") or "pending","status_label":_status_label(t.get("status")),"priority":t.get("priority") or "medium","priority_label":_priority_label(t.get("priority")),"deadline":t.get("deadline") or "","category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"} for t in selected]
    elif section=="calendar":
        result["rows"]=[{"id":t.get("id"),"title":t.get("title") or "بدون عنوان","status_label":_status_label(t.get("status")),"priority":t.get("priority") or "medium","priority_label":_priority_label(t.get("priority")),"deadline":t.get("deadline") or "","category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"} for t in sorted([x for x in tasks if x.get("deadline")],key=lambda x:x.get("deadline") or "")]
    elif section=="status":result["rows"]=[{"status":_status_label(k),"count":v} for k,v in statuses.most_common()]
    elif section=="priority":result["rows"]=[{"priority":_priority_label(k),"count":v} for k,v in priorities.most_common()]
    elif section in {"category","categories"}:result["rows"]=[{"category":k,"count":v} for k,v in cats.most_common()]
    return result

def report_section(token,section,page=1,page_size=25):
    data=monthly_report(token,section)
    if data is None:return None
    if section in {"tasks","deadlines","calendar"} and "rows" in data:
        rows=data["rows"]; total=len(rows); page=max(1,int(page)); start=(page-1)*page_size; data["rows"]=rows[start:start+page_size]; data.update({"page":page,"page_size":page_size,"total":total,"pages":max(1,(total+page_size-1)//page_size)})
    return data
