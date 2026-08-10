from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.database import fetch_all, fetch_one, execute, get_db, init_db, _run

DEFAULT_TIMEZONE = "UTC"
DEFAULT_DATE_FORMAT = "jalali"

async def init_users():
    await init_db()

async def read_users_async():
    rows = await fetch_all("users")
    for row in rows:
        row["user_id"] = str(row.get("user_id", ""))
        row["messages_count"] = str(row.get("messages_count") or 0)
        row["date_format"] = row.get("date_format") or DEFAULT_DATE_FORMAT
    return rows

def read_users():
    return _run(read_users_async())

def validate_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo((tz_name or "").strip())
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False

async def record_user_async(user, increment_usage=True):
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

def record_user(user, increment_usage=True):
    """Legacy sync facade. Async handlers should await record_user_async()."""
    return _run(record_user_async(user, increment_usage))

async def set_user_timezone_async(user_id, tz_name: str) -> bool:
    tz_name = (tz_name or "").strip()
    if not validate_timezone(tz_name):
        return False
    await execute(
        "INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0) "
        "ON CONFLICT(user_id) DO UPDATE SET timezone=excluded.timezone",
        (str(user_id), tz_name, DEFAULT_DATE_FORMAT),
    )
    return True

def set_user_timezone(user_id, tz_name: str) -> bool:
    return _run(set_user_timezone_async(user_id, tz_name))

async def get_user_timezone_async(user_id):
    row = await fetch_one("users", "user_id=?", (str(user_id),))
    return (row or {}).get("timezone") or DEFAULT_TIMEZONE

def get_user_timezone(user_id):
    return _run(get_user_timezone_async(user_id))

async def set_user_date_format_async(user_id, date_format):
    value = (date_format or "").strip().lower()
    if value not in {"jalali", "gregorian"}:
        return False
    await execute(
        "INSERT INTO users(user_id,date_format,timezone,messages_count) VALUES(?,?,?,0) "
        "ON CONFLICT(user_id) DO UPDATE SET date_format=excluded.date_format",
        (str(user_id), value, DEFAULT_TIMEZONE),
    )
    return True

def set_user_date_format(user_id, date_format):
    return _run(set_user_date_format_async(user_id, date_format))

async def get_user_date_format_async(user_id):
    value = ((await fetch_one("users", "user_id=?", (str(user_id),)) or {}).get("date_format") or DEFAULT_DATE_FORMAT).lower()
    return value if value in {"jalali", "gregorian"} else DEFAULT_DATE_FORMAT

def get_user_date_format(user_id):
    return _run(get_user_date_format_async(user_id))

def all_users():
    return read_users()
