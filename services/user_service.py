from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.database import fetch_all, fetch_one, execute, get_db, init_db

DEFAULT_TIMEZONE = "UTC"
DEFAULT_DATE_FORMAT = "jalali"

async def init_users():
    await init_db()

async def read_users():
    rows = await fetch_all("users")
    for row in rows:
        row["user_id"] = str(row.get("user_id", ""))
        row["messages_count"] = str(row.get("messages_count") or 0)
        row["date_format"] = row.get("date_format") or DEFAULT_DATE_FORMAT
    return rows

def validate_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo((tz_name or "").strip())
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False

async def record_user(user, increment_usage=True):
    """Atomic user upsert with correct new-user detection."""
    if not user:
        return False
    uid = str(user.id)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    increment = 1 if increment_usage else 0
    db = await get_db()
    async with db.lock:
        cur = await db.conn.execute(
            """INSERT OR IGNORE INTO users(
                user_id,full_name,username,timezone,date_format,first_seen,last_seen,messages_count
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (uid, user.full_name or "", user.username or "", DEFAULT_TIMEZONE,
             DEFAULT_DATE_FORMAT, now, now, increment),
        )
        is_new = cur.rowcount == 1
        if not is_new:
            await db.conn.execute(
                """UPDATE users SET full_name=?,username=?,last_seen=?,messages_count=messages_count+?
                   WHERE user_id=?""",
                (user.full_name or "", user.username or "", now, increment, uid),
            )
        await db.conn.commit()
    return is_new

async def set_user_timezone(user_id, tz_name: str) -> bool:
    tz_name = (tz_name or "").strip()
    if not validate_timezone(tz_name):
        return False
    uid = str(user_id)
    await execute(
        "INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0) "
        "ON CONFLICT(user_id) DO UPDATE SET timezone=excluded.timezone",
        (uid, tz_name, DEFAULT_DATE_FORMAT),
    )
    return True

async def get_user_timezone(user_id):
    row = await fetch_one("users", "user_id=?", (str(user_id),))
    return (row or {}).get("timezone") or DEFAULT_TIMEZONE

async def set_user_date_format(user_id, date_format):
    value = (date_format or "").strip().lower()
    if value not in {"jalali", "gregorian"}:
        return False
    uid = str(user_id)
    await execute(
        "INSERT INTO users(user_id,date_format,timezone,messages_count) VALUES(?,?,?,0) "
        "ON CONFLICT(user_id) DO UPDATE SET date_format=excluded.date_format",
        (uid, value, DEFAULT_TIMEZONE),
    )
    return True

async def get_user_date_format(user_id):
    value = ((await fetch_one("users", "user_id=?", (str(user_id),)) or {}).get("date_format") or DEFAULT_DATE_FORMAT).lower()
    return value if value in {"jalali", "gregorian"} else DEFAULT_DATE_FORMAT

async def all_users():
    return await read_users()
