"""Admin dashboard and management API helpers."""
from __future__ import annotations
import os, platform, resource, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from services.database import get_db
from services.bot_feature_registry import DEFAULT_PROFILE_TEMPLATES
from services.bot_permission_registry import default_permission_policy
from services.bot_runtime_status import get_runtime_status, list_runtime_statuses
from services.bot_management_service import (
    create_managed_bot,
    feature_registry_payload,
    get_managed_bot,
    list_audit_events,
    list_managed_bots,
    permissions_registry_payload,
    seed_default_profiles,
    set_bot_status,
    update_managed_bot,
    validate_token_only,
)

DB_PATH=Path("data/data.db")
_STARTED_AT=time.time()
def _since(days:int)->str:return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
def _user_scope(bot_key: str) -> tuple[str, list[str]]:
    """Restrict bot-specific lists to creators OR assignees of general tasks.

    Clinic/workspace records are intentionally outside the generic back office
    user/task explorer; they require vertical-specific permissions.
    """
    if not bot_key:
        return "", []
    return (
        """WHERE EXISTS (
             SELECT 1 FROM tasks t
             WHERE t.workspace_id IS NULL AND t.bot_key=?
               AND (t.user_id=u.user_id OR t.assignee_id=u.user_id)
           )""",
        [bot_key],
    )


def _task_count_columns(bot_key: str) -> tuple[str, list[str]]:
    bot_clause = " AND t.bot_key=?" if bot_key else ""
    sql = (
        "(SELECT COUNT(*) FROM tasks t WHERE t.workspace_id IS NULL "
        "AND t.user_id=u.user_id" + bot_clause + ") AS task_count, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.workspace_id IS NULL "
        "AND t.assignee_id=u.user_id" + bot_clause + ") AS assigned_task_count"
    )
    return sql, ([bot_key, bot_key] if bot_key else [])


async def list_users(bot_key: str = "", search: str = "", limit: int = 50, offset: int = 0) -> dict:
    db = await get_db()
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    clauses, params = _user_scope(bot_key)
    if search.strip():
        clauses += (" AND " if clauses else " WHERE ") + (
            "(u.full_name LIKE ? OR u.username LIKE ? OR u.user_id LIKE ?)"
        )
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    async with db.conn.execute(
        f"SELECT COUNT(*) FROM users u {clauses}", tuple(params)  # nosec B608 - static filter fragments and bound values
    ) as cur:
        total = (await cur.fetchone())[0]

    count_columns, count_args = _task_count_columns(bot_key)
    query = (
        "SELECT u.user_id,u.full_name,u.username,u.first_seen,u.last_seen,"
        "(SELECT COUNT(*) FROM team_members tm WHERE tm.user_id=u.user_id) AS team_count,"
        + count_columns + " FROM users u " + clauses
        + " ORDER BY COALESCE(u.last_seen,u.first_seen) DESC,u.user_id"
        + " LIMIT ? OFFSET ?"
    )
    # SELECT count subqueries appear BEFORE the WHERE filter placeholders.
    # Preserve SQL placeholder order even when search and bot filters coexist.
    query_args = tuple(count_args + params + [limit, offset])
    async with db.conn.execute(query, query_args) as cur:  # nosec B608 - fixed clauses and bound params
        users = [dict(row) for row in await cur.fetchall()]
    return {"users": users, "total": total, "limit": limit, "offset": offset}


async def get_user_profile(user_id: str, bot_key: str = "") -> dict | None:
    db = await get_db()
    count_columns, count_args = _task_count_columns(bot_key)
    scope, scope_args = _user_scope(bot_key)
    if scope:
        scope += " AND u.user_id=?"
        where_args = scope_args + [user_id]
    else:
        scope = "WHERE u.user_id=?"
        where_args = [user_id]
    query = (
        "SELECT u.*,"
        "(SELECT COUNT(*) FROM team_members tm WHERE tm.user_id=u.user_id) AS team_count,"
        + count_columns + " FROM users u " + scope
    )
    async with db.conn.execute(query, tuple(count_args + where_args)) as cur:  # nosec B608 - only fixed predicates and bound parameters
        row = await cur.fetchone()
    return dict(row) if row else None


async def list_user_tasks_page(
    user_id: str, bot_key: str = "", *, view: str = "created",
    limit: int = 25, offset: int = 0,
) -> dict:
    """Paginate created OR currently assigned general tasks for an admin user.

    A self-assigned task may appear in both tabs. Neither tab touches patient,
    clinic or other workspace data.
    """
    if view not in {"created", "assigned"}:
        raise ValueError("invalid_user_task_view")
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    column = "user_id" if view == "created" else "assignee_id"
    clause = " AND bot_key=?" if bot_key else ""
    params = (str(user_id), bot_key) if bot_key else (str(user_id),)
    db = await get_db()
    where = f"workspace_id IS NULL AND {column}=?{clause}"
    async with db.conn.execute(
        f"SELECT COUNT(*) FROM tasks WHERE {where}", params  # nosec B608 - whitelisted column and bound values
    ) as cur:
        total = (await cur.fetchone())[0]
    async with db.conn.execute(
        "SELECT id,title,priority,status,deadline,category,tags,"
        "created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username,"
        "user_id,bot_key FROM tasks WHERE " + where
        + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
        params + (limit, offset),
    ) as cur:
        rows = [dict(row) for row in await cur.fetchall()]
    return {
        "tasks": rows, "total": total, "limit": limit, "offset": offset,
        "view": view, "user_id": str(user_id),
    }


async def list_user_tasks(user_id: str, bot_key: str = "") -> list[dict]:
    """Legacy internal list contract; the HTTP handler uses bounded pages.

    Retain this return shape for existing integrations and Healthcare isolation
    tests, while keeping the public admin API bounded via list_user_tasks_page.
    """
    db = await get_db()
    scope = " AND bot_key=?" if bot_key else ""
    params = (str(user_id), bot_key) if bot_key else (str(user_id),)
    async with db.conn.execute(
        "SELECT id,title,priority,status,deadline,category,tags,created_at,"
        "completed_at,team_id,assignee_id,assignee_name,assignee_username "
        "FROM tasks WHERE workspace_id IS NULL AND user_id=?" + scope
        + " ORDER BY created_at DESC", params
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


async def dashboard_stats(bot_key:str="")->dict:
    db=await get_db(); task_scope="WHERE workspace_id IS NULL AND bot_key=?" if bot_key else "WHERE workspace_id IS NULL"; tp=[bot_key] if bot_key else []; uf,up=_user_scope(bot_key)
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {uf}",tuple(up)) as c: total=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} first_seen>=?",(*up,_since(7))) as c:new=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} last_seen>=?",(*up,_since(30))) as c:active=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM tasks {task_scope}",tuple(tp)) as c:tasks=(await c.fetchone())[0]
    async with db.conn.execute(f"SELECT bot_key,COUNT(DISTINCT user_id) AS users FROM tasks {task_scope} GROUP BY bot_key ORDER BY users DESC",tuple(tp)) as c:bots=[dict(r) for r in await c.fetchall()]
    latest_columns, latest_args = _task_count_columns(bot_key)
    latest_query = (
        "SELECT u.user_id,u.full_name,u.username,u.first_seen,u.last_seen,"
        + latest_columns + " FROM users u " + uf
        + " ORDER BY COALESCE(u.last_seen,u.first_seen) DESC,u.user_id LIMIT 10"
    )
    async with db.conn.execute(latest_query, tuple(latest_args + up)) as c:  # nosec B608 - bound params
        latest = [dict(r) for r in await c.fetchall()]
    guest_sql=f"SELECT COUNT(*) FROM users u {uf} {'AND' if uf else 'WHERE'} NOT EXISTS (SELECT 1 FROM team_members tm WHERE tm.user_id=u.user_id)"
    async with db.conn.execute(guest_sql,tuple(up)) as c:guest=(await c.fetchone())[0]
    async with db.conn.execute("SELECT bot_key,bot_username,owner_name,status FROM custom_bots ORDER BY created_at DESC") as c:active_bots=[dict(r) for r in await c.fetchall()]
    known={x['bot_key'] for x in active_bots}
    async with db.conn.execute("SELECT DISTINCT bot_key FROM tasks WHERE workspace_id IS NULL AND bot_key!=''") as c:
        for (key,) in await c.fetchall():
            if key not in known: active_bots.append({'bot_key':key,'bot_username':'','owner_name':'','status':'active'})
    return {'users':{'total':total,'new_7_days':new,'active_30_days':active,'guest':guest},'tasks':{'total':tasks},'bots':bots,'active_bots':{'count':len(active_bots),'items':active_bots},'database':{'status':'ok'},'latest_users':latest,'bot_key':bot_key}
async def task_status_distribution(bot_key:str="")->list[dict]:
    db=await get_db()
    scope="WHERE workspace_id IS NULL AND bot_key=?" if bot_key else "WHERE workspace_id IS NULL"
    params=(bot_key,) if bot_key else ()
    statuses=("pending","in_progress","done","cancelled")
    async with db.conn.execute(f"SELECT status,COUNT(*) AS count FROM tasks {scope} GROUP BY status",params) as c:
        counts={row["status"]:int(row["count"] or 0) for row in await c.fetchall()}
    total=sum(counts.get(status,0) for status in statuses)
    return [{"status":status,"count":counts.get(status,0),"percentage":round((counts.get(status,0)/total)*100,1) if total else 0} for status in statuses]
async def bot_management()->list[dict]:
    await seed_default_profiles()
    rows = await list_managed_bots()
    runtime_statuses = await list_runtime_statuses()
    db = await get_db()
    async with db.conn.execute("SELECT bot_key,COUNT(DISTINCT user_id) AS users,COUNT(*) AS tasks,MAX(created_at) AS last_activity FROM tasks WHERE workspace_id IS NULL GROUP BY bot_key") as cur:
        stats={r["bot_key"]:dict(r) for r in await cur.fetchall()}
    known={r["bot_key"] for r in rows}
    for key in stats:
        if key not in known:
            rows.append({
                "bot_key":key,"bot_username":"","owner_user_id":"","owner_name":"",
                "owner_username":"","status":"active","created_at":"","updated_at":"",
                "display_name":key,"description":"","profile_type":"legacy","base_profile":"",
                "features":[],"enabled_feature_count":0,"token_configured":False,"token_masked":"",
                "source":"runtime","last_error":"","last_connectivity_check":"",
                "settings":{},"permissions":{},"commands":[],"workflow":{},"menu":[]
            })
    for row in rows:
        s=stats.get(row["bot_key"],{})
        row["users"]=s.get("users",0)
        row["tasks"]=s.get("tasks",0)
        row["last_activity"]=s.get("last_activity","")
        row["status"]=row.get("status") or "inactive"
        runtime=runtime_statuses.get(row["bot_key"],{})
        row["runtime_status"]=runtime.get("runtime_status","unknown")
        row["runtime_desired_status"]=runtime.get("desired_status",row["status"])
        row["last_runtime_start"]=runtime.get("last_started_at","")
        row["last_runtime_stop"]=runtime.get("last_stopped_at","")
        row["last_runtime_reload"]=runtime.get("last_reloaded_at","")
        row["runtime_error"]=runtime.get("last_error","")
        row["runtime_error_at"]=runtime.get("last_error_at","")
    return rows


async def bot_feature_registry()->dict:
    await seed_default_profiles()
    profiles=[
        {
            "key":key,
            "label":template["name"],
            "features":list(template["features"]),
            "permissions":default_permission_policy(template["features"]),
        }
        for key,template in DEFAULT_PROFILE_TEMPLATES.items()
    ]
    custom_features=["core","tasks"]
    profiles.append({
        "key":"custom",
        "label":"Custom",
        "features":custom_features,
        "permissions":default_permission_policy(custom_features),
    })
    return {
        "features":feature_registry_payload(),
        "permissions":permissions_registry_payload(),
        "profiles":profiles,
    }


async def get_bot_management_detail(bot_key:str)->dict|None:
    await seed_default_profiles()
    bot=await get_managed_bot(bot_key)
    if bot is None:
        return None
    runtime=await get_runtime_status(bot_key) or {}
    bot["runtime_status"]=runtime.get("runtime_status","unknown")
    bot["runtime_desired_status"]=runtime.get("desired_status",bot.get("status","inactive"))
    bot["last_runtime_start"]=runtime.get("last_started_at","")
    bot["last_runtime_stop"]=runtime.get("last_stopped_at","")
    bot["last_runtime_reload"]=runtime.get("last_reloaded_at","")
    bot["runtime_error"]=runtime.get("last_error","")
    bot["runtime_error_at"]=runtime.get("last_error_at","")
    return bot


async def create_bot_management(payload:dict,actor_user_id:object)->dict:
    return await create_managed_bot(payload,actor_user_id)


async def update_bot_management(bot_key:str,payload:dict,actor_user_id:object)->dict:
    return await update_managed_bot(bot_key,payload,actor_user_id)


async def activate_bot_management(bot_key:str,actor_user_id:object)->dict:
    return await set_bot_status(bot_key,True,actor_user_id)


async def deactivate_bot_management(bot_key:str,actor_user_id:object)->dict:
    return await set_bot_status(bot_key,False,actor_user_id)


async def validate_bot_management_token(payload:dict)->dict:
    token=str(payload.get("bot_token") or "").strip()
    if not token:
        raise ValueError("bot_token_required")
    return await validate_token_only(token)


async def bot_management_audit(bot_key:str)->list[dict]:
    return await list_audit_events(bot_key)

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
    async with db.conn.execute(f"SELECT substr(created_at,1,10) AS day,COUNT(*) AS count FROM tasks WHERE workspace_id IS NULL AND created_at>=? {scope} GROUP BY day ORDER BY day",tuple(params)) as c:rows=[dict(r) for r in await c.fetchall()]
    counts={r['day']:r['count'] for r in rows};return [{'date':(start+timedelta(days=i)).date().isoformat(),'count':counts.get((start+timedelta(days=i)).date().isoformat(),0)} for i in range(days)]
