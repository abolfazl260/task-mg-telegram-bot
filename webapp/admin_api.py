"""Admin dashboard and management API helpers."""
from __future__ import annotations
import os, platform, resource, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from services.database import get_db

DB_PATH=Path("data/data.db")
_STARTED_AT=time.time()
def _since(days:int)->str:return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
def _user_scope(bot_key:str)->tuple[str,list[str]]: return ("WHERE u.user_id IN (SELECT DISTINCT user_id FROM tasks WHERE bot_key = ?)",[bot_key]) if bot_key else ("",[])
async def list_users(bot_key:str="",search:str="",limit:int=50,offset:int=0)->dict:
    db=await get_db(); limit=max(1,min(limit,100)); offset=max(0,offset); clauses,params=_user_scope(bot_key)
    if search.strip(): clauses+=(" AND " if clauses else " WHERE ")+"(u.full_name LIKE ? OR u.username LIKE ? OR u.user_id LIKE ?)"; term=f"%{search.strip()}%"; params += [term,term,term]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {clauses}",tuple(params)) as cur: total=(await cur.fetchone())[0]
    bot_task=" AND t.bot_key=?" if bot_key else ""; q=f"SELECT u.user_id,u.full_name,u.username,u.first_seen,u.last_seen,(SELECT COUNT(*) FROM team_members tm WHERE tm.user_id=u.user_id) AS team_count,(SELECT COUNT(*) FROM tasks t WHERE t.user_id=u.user_id{bot_task}) AS task_count FROM users u {clauses} ORDER BY COALESCE(u.last_seen,u.first_seen) DESC LIMIT ? OFFSET ?"; qp=list(params)+([bot_key] if bot_key else [])+[limit,offset]
    async with db.conn.execute(q,tuple(qp)) as cur: users=[dict(r) for r in await cur.fetchall()]
    return {"users":users,"total":total,"limit":limit,"offset":offset}
async def get_user_profile(user_id:str,bot_key:str="")->dict|None:
    db=await get_db(); scope="AND EXISTS (SELECT 1 FROM tasks tb WHERE tb.user_id=u.user_id AND tb.bot_key=?)" if bot_key else ""; task=" AND t.bot_key=?" if bot_key else ""; params=[user_id]+([bot_key] if bot_key else [])+([bot_key] if bot_key else [])
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
    guest_sql=f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} NOT EXISTS (SELECT 1 FROM team_members tm WHERE tm.user_id=u.user_id)"
    async with db.conn.execute(guest_sql,tuple(up)) as c:guest=(await c.fetchone())[0]
    async with db.conn.execute("SELECT bot_key,bot_username,owner_name,status FROM custom_bots ORDER BY created_at DESC") as c:active_bots=[dict(r) for r in await c.fetchall()]
    known={x['bot_key'] for x in active_bots}
    async with db.conn.execute("SELECT DISTINCT bot_key FROM tasks WHERE bot_key!=''") as c:
        for (key,) in await c.fetchall():
            if key not in known: active_bots.append({'bot_key':key,'bot_username':'','owner_name':'','status':'active'})
    return {'users':{'total':total,'new_7_days':new,'active_30_days':active,'guest':guest},'tasks':{'total':tasks},'bots':bots,'active_bots':{'count':len(active_bots),'items':active_bots},'database':{'status':'ok'},'latest_users':latest,'bot_key':bot_key}
async def task_status_distribution(bot_key:str="")->list[dict]:
    db=await get_db()
    scope="WHERE bot_key=?" if bot_key else ""
    params=(bot_key,) if bot_key else ()
    statuses=("pending","in_progress","done","cancelled")
    async with db.conn.execute(f"SELECT status,COUNT(*) AS count FROM tasks {scope} GROUP BY status",params) as c:
        counts={row["status"]:int(row["count"] or 0) for row in await c.fetchall()}
    total=sum(counts.get(status,0) for status in statuses)
    return [{"status":status,"count":counts.get(status,0),"percentage":round((counts.get(status,0)/total)*100,1) if total else 0} for status in statuses]
async def bot_management()->list[dict]:
    db=await get_db()
    async with db.conn.execute("SELECT bot_key,bot_username,owner_user_id,owner_name,owner_username,status,created_at,updated_at FROM custom_bots ORDER BY created_at DESC") as c: rows=[dict(r) for r in await c.fetchall()]
    async with db.conn.execute("SELECT bot_key,COUNT(DISTINCT user_id) AS users,COUNT(*) AS tasks,MAX(created_at) AS last_activity FROM tasks GROUP BY bot_key") as c: stats={r['bot_key']:dict(r) for r in await c.fetchall()}
    known={r['bot_key'] for r in rows}
    for key in stats:
        if key not in known: rows.append({'bot_key':key,'bot_username':'','owner_user_id':'','owner_name':'','owner_username':'','status':'active','created_at':'','updated_at':''})
    for r in rows:
        s=stats.get(r['bot_key'],{}); r['users']=s.get('users',0); r['tasks']=s.get('tasks',0); r['last_activity']=s.get('last_activity',''); r['status']=r.get('status') or 'inactive'
    return rows
async def system_health()->dict:
    db=await get_db(); tables=[]; records={}; db_size=DB_PATH.stat().st_size if DB_PATH.exists() else 0
    try:
        async with db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") as c: tables=[r[0] for r in await c.fetchall()]
        for table in tables:
            async with db.conn.execute(f'SELECT COUNT(*) FROM "{table}"') as c: records[table]=(await c.fetchone())[0]
        db_status='healthy'
    except Exception as exc: db_status=f'error: {type(exc).__name__}'
    bots=await bot_management(); active=sum(1 for b in bots if str(b.get('status')).lower()=='active')
    try: load1,_,_=os.getloadavg()
    except Exception: load1=0
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system()!='Darwin': rss=int(rss*1024)
    errors=[]
    for p in (Path('logs'),Path('log')):
        if p.exists():
            for f in sorted(p.glob('*.log'),key=lambda x:x.stat().st_mtime,reverse=True)[:3]:
                try:
                    lines=f.read_text(errors='ignore').splitlines()
                    errors += [{'source':f.name,'message':x[-500:]} for x in lines if 'ERROR' in x.upper() or 'TRACEBACK' in x.upper()][-5:]
                except Exception: pass
    return {'database':{'status':db_status,'size_bytes':db_size,'size_mb':round(db_size/1048576,2),'records':records,'total_records':sum(records.values())},'bots':{'status':'healthy' if active else 'inactive','active':active,'total':len(bots)},'api':{'status':'healthy','endpoint':'/healthz'},'recent_errors':errors[-10:],'uptime_seconds':round(time.time()-_STARTED_AT,1),'server':{'platform':platform.platform(),'cpu_count':os.cpu_count() or 1,'load_1m':load1,'memory_rss_bytes':rss}}
async def task_creation(days:int,bot_key:str="")->list[dict]:
    days=30 if days>7 else 7; db=await get_db();start=datetime.now(timezone.utc)-timedelta(days=days-1);scope="AND bot_key=?" if bot_key else "";params=[start.isoformat()]+([bot_key] if bot_key else [])
    async with db.conn.execute(f"SELECT substr(created_at,1,10) AS day,COUNT(*) AS count FROM tasks WHERE created_at>=? {scope} GROUP BY day ORDER BY day",tuple(params)) as c:rows=[dict(r) for r in await c.fetchall()]
    counts={r['day']:r['count'] for r in rows};return [{'date':(start+timedelta(days=i)).date().isoformat(),'count':counts.get((start+timedelta(days=i)).date().isoformat(),0)} for i in range(days)]
