"""Admin dashboard and user-management API queries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.database import get_db


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _user_scope(bot_key: str) -> tuple[str, list[str]]:
    if bot_key:
        return "WHERE u.user_id IN (SELECT DISTINCT user_id FROM tasks WHERE bot_key = ?)", [bot_key]
    return "", []


async def dashboard_stats(bot_key: str = "") -> dict:
    db = await get_db()
    scope = "WHERE t.bot_key = ?" if bot_key else ""
    params: list[str] = [bot_key] if bot_key else []
    user_scope, user_params = _user_scope(bot_key)

    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {user_scope}", tuple(user_params)) as cur:
        total_users = (await cur.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {user_scope} {'AND' if user_scope else 'WHERE'} first_seen >= ?", (*user_params, _since(7))) as cur:
        new_users = (await cur.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {user_scope} {'AND' if user_scope else 'WHERE'} last_seen >= ?", (*user_params, _since(30))) as cur:
        active_users = (await cur.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM tasks t {scope}", tuple(params)) as cur:
        total_tasks = (await cur.fetchone())[0]
    async with db.conn.execute(f"SELECT bot_key, COUNT(DISTINCT user_id) AS users FROM tasks {scope} GROUP BY bot_key ORDER BY users DESC", tuple(params)) as cur:
        bot_rows = [dict(r) for r in await cur.fetchall()]
    async with db.conn.execute(f"SELECT u.user_id, u.full_name, u.username, u.first_seen, u.last_seen FROM users u {user_scope} ORDER BY u.first_seen DESC LIMIT 10", tuple(user_params)) as cur:
        latest_users = [dict(r) for r in await cur.fetchall()]

    return {"users": {"total": total_users, "new_7_days": new_users, "active_30_days": active_users}, "tasks": {"total": total_tasks}, "bots": bot_rows, "latest_users": latest_users, "bot_key": bot_key}


async def list_users(bot_key: str = "", search: str = "", limit: int = 50, offset: int = 0) -> dict:
    """Return paginated users with team/task counts and searchable identity fields."""
    db = await get_db()
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    scope, scope_params = _user_scope(bot_key)
    search = search.strip()
    search_clause = ""
    search_params: list[str] = []
    if search:
        search_clause = " AND (u.full_name LIKE ? OR u.username LIKE ? OR u.user_id LIKE ?)"
        needle = f"%{search}%"
        search_params = [needle, needle, needle]

    select_params = scope_params + search_params + ([bot_key] if bot_key else [])
    async with db.conn.execute(
        f"""
        SELECT u.user_id, u.full_name, u.username, u.first_seen, u.last_seen,
               (SELECT COUNT(*) FROM team_members tm WHERE tm.user_id = u.user_id) AS team_count,
               (SELECT COUNT(*) FROM tasks t WHERE t.user_id = u.user_id {('AND t.bot_key = ?' if bot_key else '')}) AS task_count
        FROM users u {scope}{search_clause}
        ORDER BY COALESCE(NULLIF(u.last_seen, ''), u.first_seen) DESC, u.user_id
        LIMIT ? OFFSET ?
        """,
        tuple(select_params + [limit, offset]),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    async with db.conn.execute(f"SELECT COUNT(*) FROM users u {scope}{search_clause}", tuple(scope_params + search_params)) as cur:
        total = (await cur.fetchone())[0]
    return {"users": rows, "total": total, "limit": limit, "offset": offset, "search": search, "bot_key": bot_key}


async def get_user_profile(user_id: str, bot_key: str = "") -> dict | None:
    db = await get_db()
    task_filter = "AND t.bot_key = ?" if bot_key else ""
    scope = "AND EXISTS (SELECT 1 FROM tasks tx WHERE tx.user_id = u.user_id AND tx.bot_key = ?)" if bot_key else ""
    params = ([bot_key] if bot_key else []) + [user_id] + ([bot_key] if bot_key else [])
    async with db.conn.execute(
        f"""
        SELECT u.user_id, u.full_name, u.username, u.timezone, u.date_format,
               u.first_seen, u.last_seen, u.messages_count,
               (SELECT COUNT(*) FROM team_members tm WHERE tm.user_id = u.user_id) AS team_count,
               (SELECT COUNT(*) FROM tasks t WHERE t.user_id = u.user_id {task_filter}) AS task_count
        FROM users u WHERE u.user_id = ? {scope}
        """,
        tuple(params),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def list_user_tasks(user_id: str, bot_key: str = "", limit: int = 100) -> list[dict]:
    db = await get_db()
    limit = max(1, min(limit, 200))
    conditions = ["t.user_id = ?"]
    params: list[str] = [user_id]
    if bot_key:
        conditions.append("t.bot_key = ?")
        params.append(bot_key)
    async with db.conn.execute(
        f"""
        SELECT t.id, t.bot_key, t.title, t.priority, t.status, t.deadline,
               t.category, t.tags, t.description, t.created_at, t.completed_at,
               t.team_id, t.assignee_id, t.assignee_name, t.assignee_username
        FROM tasks t WHERE {' AND '.join(conditions)}
        ORDER BY CASE WHEN t.status IN ('done','cancelled') THEN 1 ELSE 0 END,
                 CASE WHEN t.deadline = '' THEN 1 ELSE 0 END, t.deadline DESC, t.created_at DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def task_creation(days: int, bot_key: str = "") -> list[dict]:
    days = 30 if days > 7 else 7
    db = await get_db()
    start = datetime.now(timezone.utc) - timedelta(days=days - 1)
    scope = "AND bot_key = ?" if bot_key else ""
    params: list[str] = [start.isoformat()]
    if bot_key:
        params.append(bot_key)
    async with db.conn.execute(f"SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count FROM tasks WHERE created_at >= ? {scope} GROUP BY day ORDER BY day", tuple(params)) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    counts = {r["day"]: r["count"] for r in rows}
    return [{"date": (start + timedelta(days=i)).date().isoformat(), "count": counts.get((start + timedelta(days=i)).date().isoformat(), 0)} for i in range(days)]
