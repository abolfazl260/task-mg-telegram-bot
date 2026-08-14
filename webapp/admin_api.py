"""Temporary unauthenticated admin dashboard API.

Authentication is intentionally omitted for this phase. The admin URL must be
protected at the deployment layer until the planned authentication phase.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from services.database import get_db


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


async def dashboard_stats(bot_key: str = "") -> dict:
    db = await get_db()
    scope = ""
    params: list[str] = []
    if bot_key:
        scope = "WHERE t.bot_key = ?"
        params.append(bot_key)

    async with db.conn.execute(f"SELECT COUNT(*) FROM users{' WHERE 1=1' if not bot_key else ' WHERE user_id IN (SELECT user_id FROM tasks WHERE bot_key = ?)'}", tuple(params if bot_key else [])) as cur:
        total_users = (await cur.fetchone())[0]

    if bot_key:
        user_scope = "WHERE user_id IN (SELECT DISTINCT user_id FROM tasks WHERE bot_key = ?)"
        user_params = [bot_key]
    else:
        user_scope = ""
        user_params = []

    async with db.conn.execute(f"SELECT COUNT(*) FROM users {user_scope} {'AND' if user_scope else 'WHERE'} first_seen >= ?", (*user_params, _since(7))) as cur:
        new_users = (await cur.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM users {user_scope} {'AND' if user_scope else 'WHERE'} last_seen >= ?", (*user_params, _since(30))) as cur:
        active_users = (await cur.fetchone())[0]
    async with db.conn.execute(f"SELECT COUNT(*) FROM tasks {scope}", tuple(params)) as cur:
        total_tasks = (await cur.fetchone())[0]

    async with db.conn.execute(f"SELECT bot_key, COUNT(DISTINCT user_id) AS users FROM tasks {scope} GROUP BY bot_key ORDER BY users DESC", tuple(params)) as cur:
        bot_rows = [dict(r) for r in await cur.fetchall()]
    async with db.conn.execute(f"SELECT user_id, full_name, username, first_seen, last_seen FROM users {user_scope} ORDER BY first_seen DESC LIMIT 10", tuple(user_params)) as cur:
        latest_users = [dict(r) for r in await cur.fetchall()]

    return {
        "users": {"total": total_users, "new_7_days": new_users, "active_30_days": active_users},
        "tasks": {"total": total_tasks},
        "bots": bot_rows,
        "latest_users": latest_users,
        "bot_key": bot_key,
    }


async def task_creation(days: int, bot_key: str = "") -> list[dict]:
    days = 30 if days > 7 else 7
    db = await get_db()
    start = datetime.now(timezone.utc) - timedelta(days=days - 1)
    scope = "AND bot_key = ?" if bot_key else ""
    params: list[str] = [start.isoformat()]
    if bot_key:
        params.append(bot_key)
    async with db.conn.execute(
        f"SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count FROM tasks WHERE created_at >= ? {scope} GROUP BY day ORDER BY day",
        tuple(params),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    counts = {r["day"]: r["count"] for r in rows}
    return [{"date": (start + timedelta(days=i)).date().isoformat(), "count": counts.get((start + timedelta(days=i)).date().isoformat(), 0)} for i in range(days)]
