from __future__ import annotations

import json
import uuid
from datetime import datetime

from bot_context import get_current_bot_key
from services.database import fetch_all, fetch_one, execute, transaction, sync_all, sync_execute
from services.team_service import aget_user_teams, acan_edit, ais_member, aget_team

VALID_STATUSES = {"pending", "in_progress", "done", "cancelled"}

def _now(): return datetime.now().strftime("%Y-%m-%d %H:%M")
def _bot(): return get_current_bot_key() or "default"

async def _ensure_user_async(uid):
    uid=str(uid or "")
    if uid: await execute("INSERT OR IGNORE INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)",(uid,"UTC","jalali"))

async def read_tasks_async(): return await fetch_all("tasks","bot_key=?",(_bot(),))

async def save_task_async(data):
    v=list(data)+[""]*20; task_id=str(v[0] or uuid.uuid4().hex[:8]); user_id=str(v[1] or "")
    if not user_id: raise ValueError("task user_id is required")
    await _ensure_user_async(user_id)
    if v[12]: await _ensure_user_async(v[12])
    await execute("""INSERT INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(task_id,_bot(),user_id,v[2] or "",v[3] or "medium",v[4] or "pending",v[5] or "",v[6] or "",v[7] or "",v[8] or "",v[9] or "",v[10] or "",v[11] or None,v[12] or None,v[13] or "",v[14] or ""))
    return task_id

async def update_task_status_async(task_id,new_status):
    if new_status not in VALID_STATUSES: return False
    if not await fetch_one("tasks","id=? AND bot_key=?",(task_id,_bot())): return False
    await execute("UPDATE tasks SET status=?,completed_at=? WHERE id=? AND bot_key=?",(new_status,_now() if new_status=="done" else "",task_id,_bot())); return True

async def create_task_async(user_id,title,priority,deadline,category,tags,description="",team_id="",assignee=None):
    await _ensure_user_async(user_id); tid=str(uuid.uuid4())[:8]
    if team_id and not category:
        team=await aget_team(team_id); category=team.get("name","") if team else category
    aid=str((assignee or {}).get("user_id") or "") or None
    if aid: await _ensure_user_async(aid)
    now=_now(); statements=[("""INSERT INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(tid,_bot(),str(user_id),title,priority,"pending",deadline or "",category or "",tags or "",description or "",now,team_id or None,aid,(assignee or {}).get("display_name") or "",(assignee or {}).get("username") or ""))]
    if assignee: statements.append(("""INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)""",(tid,str(user_id),"assigned","",(assignee or {}).get("display_name") or "",now)))
    await transaction(statements); return tid

async def _visible_async(user_id,team_id=None,active=False):
    if team_id:
        if not await ais_member(team_id,user_id): return []
        where="bot_key=? AND team_id=?"+((" AND status IN ('pending','in_progress')") if active else "")
        return await fetch_all("tasks",where,(_bot(),team_id))
    teams=await aget_user_teams(user_id); ids={x["team"]["team_id"] for x in teams}; uid=str(user_id); rows=await read_tasks_async()
    return [x for x in rows if (not active or x.get("status") in ("pending","in_progress")) and ((x.get("team_id") or "") in ids or (not x.get("team_id") and str(x.get("user_id"))==uid))]

async def get_active_tasks_async(user_id,team_id=None): return await _visible_async(user_id,team_id,True)
async def get_all_user_tasks_async(user_id,team_id=None): return await _visible_async(user_id,team_id,False)
async def get_team_tasks_async(team_id,active_only=True): return await fetch_all("tasks","bot_key=? AND team_id=?"+(" AND status IN ('pending','in_progress')" if active_only else ""),(_bot(),team_id))
async def get_task_by_id_async(task_id): return await fetch_one("tasks","id=? AND bot_key=?",(task_id,_bot()))
async def user_can_modify_task_async(user_id,task): return bool(task and (await acan_edit(task.get("team_id"),user_id) if task.get("team_id") else str(task.get("user_id"))==str(user_id)))
async def change_task_status_async(task_id,new_status): return await update_task_status_async(task_id,new_status)
async def search_tasks_async(user_id,query):
    q=(query or "").strip().lower()
    if not q: return []
    return [t for t in await get_all_user_tasks_async(user_id) if q in " ".join(str(t.get(k) or "") for k in ("title","category","tags","description")).lower()]
async def get_all_user_ids_async(): return sorted({str(t.get("user_id")) for t in await read_tasks_async() if t.get("user_id")})

async def assign_task_async(task_id,assignee,actor_id,action="assigned"):
    t=await get_task_by_id_async(task_id)
    if not t: return False
    aid=str((assignee or {}).get("user_id") or "") or None
    if aid: await _ensure_user_async(aid)
    await _ensure_user_async(actor_id); now=_now()
    await transaction([("UPDATE tasks SET assignee_id=?,assignee_name=?,assignee_username=? WHERE id=? AND bot_key=?",(aid,(assignee or {}).get("display_name") or "",(assignee or {}).get("username") or "",task_id,_bot())),("""INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)""",(task_id,str(actor_id),action,t.get("assignee_name") or "",(assignee or {}).get("display_name") or "",now))]); return True
async def get_unassigned_tasks_async(user_id): return [t for t in await get_active_tasks_async(user_id) if not t.get("assignee_id")]
async def get_task_comments_async(task_id):
    out=[]
    for r in await fetch_all("task_comments","task_id=? ORDER BY id",(task_id,)):
        try: content=json.loads(r.get("content_json") or "{}")
        except Exception: content={}
        if not isinstance(content,dict): content={"content":content}
        out.append({"author_id":str(r.get("author_id") or ""),"author_name":r.get("author_name") or "کاربر","author_username":r.get("author_username") or "","created_at":r.get("created_at") or "",**content})
    return out
async def add_task_comment_async(task_id,author,content):
    if not await get_task_by_id_async(task_id): return False
    aid=str(author.get("id") or author.get("user_id") or "") or None
    if aid: await _ensure_user_async(aid)
    await execute("INSERT INTO task_comments(task_id,author_id,author_name,author_username,content_json,created_at) VALUES(?,?,?,?,?,?)",(task_id,aid,author.get("full_name") or author.get("display_name") or "کاربر",author.get("username") or "",json.dumps(content,ensure_ascii=False),_now())); return True
async def link_user_category_to_team_async(user_id,category,team_id):
    statements=[("UPDATE tasks SET team_id=? WHERE id=? AND bot_key=?",(team_id,t["id"],_bot())) for t in await get_all_user_tasks_async(user_id) if not t.get("team_id") and (t.get("category") or "").strip().lower()==(category or "").strip().lower()]
    if statements: await transaction(statements)
    return len(statements)
async def link_team_name_category_for_owner_async(team_id):
    team=await aget_team(team_id); return await link_user_category_to_team_async(team["owner_id"],team["name"],team_id) if team else 0
async def get_assignment_history_async(task_id): return await fetch_all("task_assignment_history","task_id=? ORDER BY id",(task_id,))

# Legacy compatibility. Native async handlers must use *_async APIs.
def _run(coro):
    import asyncio,threading
    try: asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(coro)
    result=[]; errors=[]
    def worker():
        try: result.append(asyncio.run(coro))
        except BaseException as e: errors.append(e)
    t=threading.Thread(target=worker,daemon=True); t.start(); t.join()
    if errors: raise errors[0]
    return result[0] if result else None

def read_tasks(): return sync_all("tasks","bot_key=?",(_bot(),))
def save_task(data): return _run(save_task_async(data))
def update_task_status(task_id,new_status): return _run(update_task_status_async(task_id,new_status))
def create_task(*a,**k): return _run(create_task_async(*a,**k))
def get_active_tasks(*a,**k): return _run(get_active_tasks_async(*a,**k))
def get_all_user_tasks(*a,**k): return _run(get_all_user_tasks_async(*a,**k))
def get_team_tasks(*a,**k): return _run(get_team_tasks_async(*a,**k))
def get_task_by_id(*a,**k): return _run(get_task_by_id_async(*a,**k))
def user_can_modify_task(*a,**k): return _run(user_can_modify_task_async(*a,**k))
def change_task_status(*a,**k): return _run(change_task_status_async(*a,**k))
def search_tasks(*a,**k): return _run(search_tasks_async(*a,**k))
def get_all_user_ids(): return _run(get_all_user_ids_async())
def assign_task(*a,**k): return _run(assign_task_async(*a,**k))
def get_unassigned_tasks(*a,**k): return _run(get_unassigned_tasks_async(*a,**k))
def get_task_comments(*a,**k): return _run(get_task_comments_async(*a,**k))
def add_task_comment(*a,**k): return _run(add_task_comment_async(*a,**k))
def link_user_category_to_team(*a,**k): return _run(link_user_category_to_team_async(*a,**k))
def link_team_name_category_for_owner(*a,**k): return _run(link_team_name_category_for_owner_async(*a,**k))
def get_assignment_history(*a,**k): return _run(get_assignment_history_async(*a,**k))
