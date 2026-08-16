"""Web report data access. Every report is scoped by its opaque report token."""
from __future__ import annotations
import calendar,json
from collections import Counter
from datetime import date,datetime,timedelta,timezone
import jdatetime
from services.database import sync_all
from .report_tokens import resolve_report_token

def _status(v): return {"pending":"شروع‌نشده","in_progress":"در حال انجام","done":"انجام‌شده","cancelled":"لغو شده","canceled":"لغو شده"}.get(v or "",v or "نامشخص")
def _priority(v): return {"high":"بالا","medium":"متوسط","low":"پایین"}.get(v or "",v or "نامشخص")
def _access(token):
    a=resolve_report_token(token); return a if a and a.get("report_type")=="monthly" else None
def _jday(d): return jdatetime.date.fromgregorian(year=d.year,month=d.month,day=d.day).strftime("%-d %B %Y")
def _jmonth(d): return jdatetime.date.fromgregorian(year=d.year,month=d.month,day=1).strftime("%B %Y")
def _month():
    n=datetime.now(timezone.utc).date(); return date(n.year,n.month,1),date(n.year,n.month,calendar.monthrange(n.year,n.month)[1])
def _previous_month(start):
    previous_end=start-timedelta(days=1); return date(previous_end.year,previous_end.month,1),previous_end
def _task_rows(a,where="",params=()):
    base="bot_key=? AND user_id=?"; return sync_all("tasks",base+(" AND "+where if where else ""),(a["bot_key"],str(a["user_id"]))+tuple(params))
def _task_count(a,start,end):
    endx=end+timedelta(days=1); return len(_task_rows(a,"created_at>=? AND created_at<?",(start.isoformat(),endx.isoformat())))
def _change(total,previous_total):
    if previous_total > 0:
        percentage=round((total-previous_total)/previous_total*100)
        direction="up" if percentage>0 else "down" if percentage<0 else "flat"
        return {"available":True,"percentage":abs(percentage),"direction":direction,"previous_total":previous_total}
    if total > 0:
        return {"available":False,"percentage":None,"direction":"new","previous_total":0}
    return {"available":False,"percentage":None,"direction":"none","previous_total":0}

def _week(a):
    today=datetime.now(timezone.utc).date(); end=today+timedelta(days=6); tasks=_task_rows(a,"deadline>=? AND deadline<?",(today.isoformat(),(end+timedelta(days=1)).isoformat())); names=["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]; days=[]
    for i in range(7):
        d=today+timedelta(days=i); rows=[]
        for t in tasks:
            raw=str(t.get("deadline") or "")
            if raw[:10]!=d.isoformat(): continue
            rows.append({"id":t.get("id"),"title":t.get("title") or "بدون عنوان","priority":t.get("priority") or "medium","priority_label":_priority(t.get("priority")),"status":t.get("status") or "pending","status_label":_status(t.get("status")),"deadline":raw,"category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"})
        rows.sort(key=lambda x:(x["deadline"],x["title"])); days.append({"offset":i,"date":d.isoformat(),"jalali":_jday(d),"weekday":names[d.weekday()],"label":"برنامه امروز" if i==0 else ("برنامه فردا" if i==1 else f"برنامه {names[d.weekday()]}"),"rows":rows,"count":len(rows)})
    return {"start":today.isoformat(),"end":end.isoformat(),"days":days,"total":len(tasks)}

def _habits(a,start,end):
    uid=str(a["user_id"]); habits=sync_all("habits","user_id=?",(uid,)); logs=sync_all("habit_logs","user_id=? AND done_date>=? AND done_date<=?",(uid,start.isoformat(),end.isoformat())); counts=Counter(str(x.get("habit_id")) for x in logs); active=[h for h in habits if h.get("active") in (1,True,"1")]; rows=[]
    for h in active:
        hid=str(h.get("id")); relevant=[x.get("done_date") for x in logs if str(x.get("habit_id"))==hid and x.get("done_date")]; rows.append({"id":hid,"title":h.get("title") or "بدون عنوان","category":h.get("category") or "بدون دسته‌بندی","target":h.get("target") or "—","repeat_type":{"daily":"روزانه","weekly":"هفتگی","monthly":"ماهانه"}.get(h.get("repeat_type"),h.get("repeat_type") or "—"),"completed":counts.get(hid,0),"last_done":max(relevant,default="—")})
    rows.sort(key=lambda x:(-x["completed"],x["title"])); bycat=Counter(x["category"] for x in rows); byday=Counter(x.get("done_date") for x in logs if x.get("done_date")); return {"total_habits":len(habits),"active_habits":len(active),"completed_logs":sum(counts.values()),"completion_days":len(byday),"rows":rows,"by_category":[{"label":k,"count":v} for k,v in bycat.most_common()],"daily_activity":[{"date":k,"count":v} for k,v in sorted(byday.items())]}

def _heatmap(a):
    n=datetime.now(timezone.utc).date(); start=date(n.year,n.month,1); nxt=date(n.year+(n.month==12),1 if n.month==12 else n.month+1,1); tasks=_task_rows(a,"deadline>=? AND deadline<? AND deadline IS NOT NULL AND deadline!=''",(start.isoformat(),nxt.isoformat())); c=Counter(str(t.get("deadline"))[:10] for t in tasks); vals=[{"day":d,"date":f"{n.year:04d}-{n.month:02d}-{d:02d}","count":c.get(f"{n.year:04d}-{n.month:02d}-{d:02d}",0)} for d in range(1,calendar.monthrange(n.year,n.month)[1]+1)]; mx=max((x["count"] for x in vals),default=0); return {"section":"heatmap","year":n.year,"month":n.month,"month_label":f"{n.year:04d}/{n.month:02d} · {_jmonth(n)}","days":vals,"max_count":mx,"total":sum(x["count"] for x in vals)}

def _recent(a):
    args=(a["bot_key"],str(a["user_id"])); tasks={str(t.get("id")):t for t in sync_all("tasks","bot_key=? AND user_id=?",args)}; events=[]
    try: comments=sync_all("task_comments","task_id IN (SELECT id FROM tasks WHERE bot_key=? AND user_id=?)",args)
    except Exception: comments=[]
    try: assigns=sync_all("task_assignment_history","task_id IN (SELECT id FROM tasks WHERE bot_key=? AND user_id=?)",args)
    except Exception: assigns=[]
    labels={"text":"کامنت ثبت کرد","photo":"تصویر ارسال کرد","voice":"پیام صوتی ارسال کرد","audio":"فایل صوتی ارسال کرد","document":"فایل ارسال کرد","video":"ویدئو ارسال کرد","animation":"گیف ارسال کرد","sticker":"استیکر ارسال کرد"}
    for r in comments:
        try: c=json.loads(r.get("content_json") or "{}")
        except Exception: c={}
        if not isinstance(c,dict): c={"content":c}; typ=c.get("type") or "text"; text=c.get("text") or c.get("caption") or c.get("file_name") or "محتوا ارسال شد"; t=tasks.get(str(r.get("task_id")),{})
        events.append({"id":f"comment-{r.get('id')}","icon":"💬","title":labels.get(typ,"کامنت ثبت کرد"),"task_id":r.get("task_id"),"task_title":t.get("title") or "بدون عنوان","actor":r.get("author_name") or "کاربر","actor_username":r.get("author_username") or "","text":str(text).replace("\n"," ")[:220],"created_at":r.get("created_at") or ""})
    for r in assigns:
        t=tasks.get(str(r.get("task_id")),{}); action=r.get("action") or "assigned"
        if action in ("unassigned","removed"): title="مسئولیت تسک را حذف کرد"; text=f"مسئول قبلی: {r.get('old_assignee_name') or '—'}"
        elif action in ("claimed","self_assigned"): title="تسک را برای خود برداشت"; text=f"مسئول: {r.get('new_assignee_name') or '—'}"
        else: title="مسئول تسک را تغییر داد"; text=f"{r.get('old_assignee_name') or 'بدون مسئول'} ← {r.get('new_assignee_name') or 'بدون مسئول'}"
        events.append({"id":f"assignment-{r.get('id')}","icon":"👤","title":title,"task_id":r.get("task_id"),"task_title":t.get("title") or "بدون عنوان","actor":r.get("actor_id") or "کاربر","text":text,"created_at":r.get("created_at") or ""})
    events.sort(key=lambda x:(x.get("created_at") or "",x.get("id") or ""),reverse=True); return {"section":"recent_changes","total":len(events),"events":events[:100]}

def monthly_report(token,section="summary"):
    a=_access(token)
    if not a:return None
    if section=="week":return {"report_type":"weekly_schedule","week":_week(a)}
    start,end=_month(); endx=end+timedelta(days=1); tasks=_task_rows(a,"created_at>=? AND created_at<?",(start.isoformat(),endx.isoformat())); statuses=Counter((t.get("status") or "pending") for t in tasks); priorities=Counter((t.get("priority") or "medium") for t in tasks); cats=Counter((t.get("category") or "بدون دسته‌بندی").strip() or "بدون دسته‌بندی" for t in tasks); total=len(tasks); done=statuses.get("done",0); cancelled=statuses.get("cancelled",statuses.get("canceled",0)); dl=[t for t in tasks if t.get("deadline")]; today=date.today().isoformat(); overdue=sum(1 for t in dl if str(t.get("deadline"))[:10]<today and t.get("status") not in {"done","cancelled","canceled"})
    previous_start,previous_end=_previous_month(start); previous_total=_task_count(a,previous_start,previous_end)
    result={"report_type":"monthly","period":{"gregorian":f"{start.isoformat()} تا {end.isoformat()}","jalali":_jmonth(start)},"summary":{"total":total,"total_change":_change(total,previous_total),"done":done,"in_progress":statuses.get("in_progress",0),"pending":statuses.get("pending",0),"cancelled":cancelled,"active":total-done-cancelled,"overdue":overdue,"with_deadline":len(dl),"without_deadline":total-len(dl),"completion_rate":round(done/total*100) if total else 0},"by_status":[{"key":k,"label":_status(k),"count":v} for k,v in statuses.most_common()],"by_priority":[{"key":k,"label":_priority(k),"count":v} for k,v in priorities.most_common()],"by_category":[{"label":k,"count":v} for k,v in cats.most_common()]}
    if section=="habits": result["habits"]=_habits(a,start,end); return result
    if section=="heatmap": return _heatmap(a)
    if section=="recent_changes": return _recent(a)
    if section=="kanban":
        cols={"pending":[],"in_progress":[],"done":[],"cancelled":[]}
        for t in sorted(tasks,key=lambda x:x.get("id") or "",reverse=True):
            k=t.get("status") or "pending"; k="cancelled" if k in {"cancelled","canceled"} else k; cols.setdefault(k,[]).append({"id":t.get("id"),"title":t.get("title") or "بدون عنوان","status_label":_status(t.get("status")),"priority":t.get("priority") or "medium","priority_label":_priority(t.get("priority")),"deadline":t.get("deadline") or "","category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"})
        return {"section":"kanban","columns":cols,"total":sum(len(v) for v in cols.values())}
    if section in {"tasks","deadlines"}:
        selected=[t for t in tasks if section=="tasks" or t.get("deadline")]; selected.sort(key=lambda x:x.get("deadline") or "9999"); result["rows"]=[{"id":t.get("id"),"title":t.get("title") or "بدون عنوان","status_label":_status(t.get("status")),"priority":t.get("priority") or "medium","priority_label":_priority(t.get("priority")),"deadline":t.get("deadline") or "","category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"} for t in selected]
    elif section=="calendar": result["rows"]=[{"id":t.get("id"),"title":t.get("title") or "بدون عنوان","status_label":_status(t.get("status")),"priority":t.get("priority") or "medium","priority_label":_priority(t.get("priority")),"deadline":t.get("deadline") or "","category":t.get("category") or "—","assignee":t.get("assignee_name") or t.get("assignee_username") or "بدون مسئول"} for t in sorted([x for x in tasks if x.get("deadline")],key=lambda x:x.get("deadline") or "")]
    elif section=="status": result["rows"]=[{"status":_status(k),"count":v} for k,v in statuses.most_common()]
    elif section=="priority": result["rows"]=[{"priority":_priority(k),"count":v} for k,v in priorities.most_common()]
    elif section in {"category","categories"}: result["rows"]=[{"category":k,"count":v} for k,v in cats.most_common()]
    return result

def report_section(token,section,page=1,page_size=25):
    data=monthly_report(token,section)
    if data is None:return None
    if section in {"tasks","deadlines","calendar"} and "rows" in data:
        page=max(1,int(page)); total=len(data["rows"]); start=(page-1)*page_size; data["rows"]=data["rows"][start:start+page_size]; data.update({"page":page,"page_size":page_size,"total":total,"pages":max(1,(total+page_size-1)//page_size)})
    return data
