"""Admin dashboard and management API helpers."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from services.database import get_db

def _since(days:int)->str:return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
def _user_scope(bot_key:str)->tuple[str,list[str]]:
    return ("WHERE u.user_id IN (SELECT DISTINCT user_id FROM tasks WHERE bot_key = ?)",[bot_key]) if bot_key else ("",[])

async def list_users(bot_key:str="",search:str="",limit:int=50,offset:int=0)->dict:
    db=await get_db(); limit=max(1,min(limit,100)); offset=max(0,offset); clauses,params=_user_scope(bot_key)
    if search.strip():
        clauses+=(" AND " if clauses else " WHERE ")+"(u.full_name LIKE ? OR u.username LIKE ? OR u.user_id LIKE ?)"; term=f"%{search.strip()}%"; params += [term,term,term]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {clauses}",tuple(params)) as cur: total=(await cur.fetchone())[0]
    bot_task=" AND t.bot_key=?" if bot_key else ""
    q=f"SELECT u.user_id,u.full_name,u.username,u.first_seen,u.last_seen,(SELECT COUNT(*) FROM team_members tm WHERE tm.user_id=u.user_id) AS team_count,(SELECT COUNT(*) FROM tasks t WHERE t.user_id=u.user_id{bot_task}) AS task_count FROM users u {clauses} ORDER BY COALESCE(u.last_seen,u.first_seen) DESC LIMIT ? OFFSET ?"
    qp=list(params)+([bot_key] if bot_key else [])+[limit,offset]
    async with db.conn.execute(q,tuple(qp)) as cur: users=[dict(r) for r in await cur.fetchall()]
    return {"users":users,"total":total,"limit":limit,"offset":offset}

async def get_user_profile(user_id:str,bot_key:str="")->dict|None:
    db=await get_db(); scope="AND EXISTS (SELECT 1 FROM tasks tb WHERE tb.user_id=u.user_id AND tb.bot_key=?)" if bot_key else ""; task=" AND t.bot_key=?" if bot_key else ""
    params=[user_id]+([bot_key] if bot_key else [])+([bot_key] if bot_key else [])
    async with db.conn.execute(f"SELECT u.*,(SELECT COUNT(*) FROM team_members tm WHERE tm.user_id=u.user_id) AS team_count,(SELECT COUNT(*) FROM tasks t WHERE t.user_id=u.user_id{task}) AS task_count FROM users u WHERE u.user_id=? {scope}",tuple(params)) as cur: row=await cur.fetchone()
    return dict(row) if row else None

async def list_user_tasks(user_id:str,bot_key:str="")->list[dict]:
    db=await get_db(); clause="AND bot_key=?" if bot_key else ""; params=[user_id]+([bot_key] if bot_key else [])
    async with db.conn.execute(f"SELECT id,title,priority,status,deadline,category,tags,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username FROM tasks WHERE user_id=? {clause} ORDER BY created_at DESC",tuple(params)) as cur:return [dict(r) for r in await cur.fetchall()]

async def dashboard_stats(bot_key:str="")->dict:
    db=await get_db(); task_scope="WHERE bot_key=?" if bot_key else ""; tp=[bot_key] if bot_key else []; uf,up=_user_scope(bot_key)
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {uf}",tuple(up)) as c: total=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} first_seen>=?",(*up,_since(7))) as c:new=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} last_seen>=?",(*up,_since(30))) as c:active=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM tasks {task_scope}",tuple(tp)) as c:tasks=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT bot_key,COUNT(DISTINCT user_id) AS users FROM tasks {task_scope} GROUP BY bot_key ORDER BY users DESC",tuple(tp)) as c:bots=[dict(r) for r in await c.fetchall()]
    async with db.conn.execute(f"SELECT user_id,full_name,username,first_seen,last_seen FROM users u {uf} ORDER BY COALESCE(last_seen,first_seen) DESC LIMIT 10",tuple(up)) as c:latest=[dict(r) for r in await c.fetchall()]
    guest_sql=f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} NOT EXISTS (SELECT 1 FROM team_members tm WHERE tm.user_id=u.user_id)"; 
    async with db.conn.execute(guest_sql,tuple(up)) as c:guest=(await c.fetchone())[0]
    async with db.conn.execute("SELECT bot_key,bot_username,owner_name,status FROM custom_bots WHERE status='active' ORDER BY created_at DESC") as c:active_bots=[dict(r) for r in await c.fetchall()]
    known={x['bot_key'] for x in active_bots}
    async with db.conn.execute("SELECT DISTINCT bot_key FROM tasks WHERE bot_key!=''") as c:
        for (key,) in await c.fetchall():
            if key not in known:active_bots.append({'bot_key':key,'bot_username':'','owner_name':'','status':'active'})
    try:
        async with db.conn.execute("SELECT 1 FROM users LIMIT 1") as c:await c.fetchone()
        db_status='ok'
    except Exception:db_status='error'
    return {'users':{'total':total,'new_7_days':new,'active_30_days':active,'guest':guest},'tasks':{'total':tasks},'bots':bots,'active_bots':{'count':len(active_bots),'items':active_bots},'database':{'status':db_status},'latest_users':latest,'bot_key':bot_key}

async def task_creation(days:int,bot_key:str="")->list[dict]:
    days=30 if days>7 else 7; db=await get_db();start=datetime.now(timezone.utc)-timedelta(days=days-1);scope="AND bot_key=?" if bot_key else "";params=[start.isoformat()]+([bot_key] if bot_key else [])
    async with db.conn.execute(f"SELECT substr(created_at,1,10) AS day,COUNT(*) AS count FROM tasks WHERE created_at>=? {scope} GROUP BY day ORDER BY day",tuple(params)) as c:rows=[dict(r) for r in await c.fetchall()]
    counts={r['day']:r['count'] for r in rows};return [{'date':(start+timedelta(days=i)).date().isoformat(),'count':counts.get((start+timedelta(days=i)).date().isoformat(),0)} for i in range(days)]
