"""Admin dashboard and management API helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
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

    user_filter = "WHERE user_id IN (SELECT DISTINCT user_id FROM tasks WHERE bot_key = ?)" if bot_key else ""
    user_params = [bot_key] if bot_key else []

    async with db.conn.execute(
        f"SELECT COUNT(*) FROM users {user_filter}", tuple(user_params)
    ) as cur:
        total_users = (await cur.fetchone())[0]

    async with db.conn.execute(
        f"SELECT COUNT(*) FROM users {user_filter} {'AND' if user_filter else 'WHERE'} first_seen >= ?",
        (*user_params, _since(7)),
    ) as cur:
        new_users = (await cur.fetchone())[0]

    async with db.conn.execute(
        f"SELECT COUNT(*) FROM users {user_filter} {'AND' if user_filter else 'WHERE'} last_seen >= ?",
        (*user_params, _since(30)),
    ) as cur:
        active_users = (await cur.fetchone())[0]

    async with db.conn.execute(f"SELECT COUNT(*) FROM tasks {scope}", tuple(params)) as cur:
        total_tasks = (await cur.fetchone())[0]

    async with db.conn.execute(
        f"SELECT bot_key, COUNT(DISTINCT user_id) AS users FROM tasks {scope} GROUP BY bot_key ORDER BY users DESC",
        tuple(params),
    ) as cur:
        bot_rows = [dict(r) for r in await cur.fetchall()]

    async with db.conn.execute(
        f"SELECT user_id, full_name, username, first_seen, last_seen FROM users {user_filter} ORDER BY first_seen DESC LIMIT 10",
        tuple(user_params),
    ) as cur:
        latest_users = [dict(r) for r in await cur.fetchall()]

    # Guest users are users who have records in the users table but no team membership.
    async with db.conn.execute(
        f"SELECT COUNT(*) FROM users u {user_filter.replace('user_id', 'u.user_id') if user_filter else ''} "
        f"{'AND' if user_filter else 'WHERE'} NOT EXISTS (SELECT 1 FROM team_members tm WHERE tm.user_id = u.user_id)",
        tuple(user_params),
    ) as cur:
        guest_users = (await cur.fetchone())[0]

    # Active bots are custom bots explicitly marked active, plus the default bot when it has task activity.
    async with db.conn.execute(
        "SELECT bot_key, bot_username, owner_name, status FROM custom_bots WHERE status = 'active' ORDER BY created_at DESC"
    ) as cur:
        active_bots = [dict(r) for r in await cur.fetchall()]

    known_bot_keys = {row.get("bot_key") for row in active_bots}
    if not bot_key:
        async with db.conn.execute(
            "SELECT DISTINCT bot_key FROM tasks WHERE bot_key != '' ORDER BY bot_key"
        ) as cur:
            task_bot_keys = [r[0] for r in await cur.fetchall()]
        for key in task_bot_keys:
            if key not in known_bot_keys:
                active_bots.append({"bot_key": key, "bot_username": "", "owner_name": "", "status": "active"})
    elif bot_key not in known_bot_keys:
        async with db.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE bot_key = ?", (bot_key,)
        ) as cur:
            if (await cur.fetchone())[0] > 0:
                active_bots.append({"bot_key": bot_key, "bot_username": "", "owner_name": "", "status": "active"})

    # Lightweight database health check: verify the connection and a core table.
    try:
        async with db.conn.execute("SELECT 1 FROM users LIMIT 1") as cur:
            await cur.fetchone()
        database_status = "ok"
    except Exception:
        database_status = "error"

    return {
        "users": {"total": total_users, "new_7_days": new_users, "active_30_days": active_users, "guest": guest_users},
        "tasks": {"total": total_tasks},
        "bots": bot_rows,
        "active_bots": {"count": len(active_bots), "items": active_bots},
        "database": {"status": database_status},
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
