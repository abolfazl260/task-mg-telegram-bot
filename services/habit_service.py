from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

from bot_context import get_current_bot_key
from services.database import execute, execute_returning_one, fetch_all, fetch_one, _run as db_run


def _bot(bot_key=None):
    return str(bot_key or get_current_bot_key() or 'default')

# قالب‌های آماده عمداً ثابت و داخل کد نگهداری می‌شوند؛ جدول جدیدی لازم نیست.
TEMPLATES = [
    {"key": "water", "title": "💧 نوشیدن آب", "target_value": 5, "target_unit": "بار در روز", "kind": "تعداد دفعات", "target": "۵ بار در روز", "repeat_type": "daily", "reminder_times": ["08:00", "11:00", "14:00", "17:00", "20:00"], "reminder_time": "08:00,11:00,14:00,17:00,20:00", "category": "سلامت", "description": "هدف ۵ بار در روز؛ یادآوری‌ها از ساعت ۸ صبح و در ساعت‌های مختلف روز."},
    {"key": "medicine", "title": "💊 یادآوری قرص", "target_value": 2, "target_unit": "بار در روز", "kind": "زمان‌بندی‌شده", "target": "۲ بار در روز", "repeat_type": "daily", "reminder_times": ["09:00", "21:00"], "reminder_time": "09:00,21:00", "category": "سلامت", "description": "دو یادآوری روزانه در ساعت ۹ صبح و ۹ شب."},
    {"key": "meditation", "title": "🧘 مدیتیشن", "target_value": 20, "target_unit": "دقیقه", "kind": "مدت زمان", "target": "۲۰ دقیقه", "repeat_type": "daily", "reminder_times": [], "reminder_time": "", "category": "سلامت", "description": "۲۰ دقیقه مدیتیشن در روز."},
    {"key": "reading", "title": "📚 مطالعه کتاب", "target_value": 30, "target_unit": "دقیقه", "kind": "مدت زمان", "target": "۳۰ دقیقه", "repeat_type": "daily", "reminder_times": [], "reminder_time": "", "category": "یادگیری", "description": "۳۰ دقیقه مطالعه کتاب در روز."},
    {"key": "gym", "title": "🏋️ باشگاه", "target_value": 30, "target_unit": "دقیقه", "kind": "مدت زمان", "target": "۳۰ دقیقه", "repeat_type": "daily", "reminder_times": [], "reminder_time": "", "category": "سلامت", "description": "۳۰ دقیقه فعالیت در باشگاه در روز."},
]


def is_habit_due_on(habit, day=None):
    day = day or date.today()
    repeat = habit.get("repeat_type") or "daily"
    try:
        start = datetime.strptime(habit.get("start_date") or date.today().isoformat(), "%Y-%m-%d").date()
    except ValueError:
        start = day
    if day < start:
        return False
    if repeat == "weekly":
        return day.weekday() == start.weekday()
    if repeat == "monthly":
        return day.day == start.day
    return True


async def _ensure_user_async(user_id):
    uid = str(user_id)
    if not await fetch_one("users", "user_id=?", (uid,)):
        await execute("INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)", (uid, "UTC", "jalali"))


def init_habits():
    from services.database import init_db
    db_run(init_db())


def _ensure_user(user_id):
    return db_run(_ensure_user_async(user_id))


async def create_habit_async(user_id, title, category="", description="", repeat_type="daily", target="", reminder_time="", start_date="", *, bot_key=None):
    await _ensure_user_async(user_id)
    hid = str(uuid.uuid4())[:8]
    await execute(
        """INSERT INTO habits(id,user_id,bot_key,title,category,description,repeat_type,target,reminder_time,start_date,active,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (hid, str(user_id), _bot(bot_key), title, category or "", description or "", repeat_type, target or "", reminder_time or "", start_date or date.today().isoformat(), 1, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
    )
    return hid


def create_habit(*args, **kwargs):
    return db_run(create_habit_async(*args, **kwargs))


async def get_user_habits_async(user_id, active_only=False, *, bot_key=None):
    return await fetch_all("habits", "bot_key=? AND user_id=?" + (" AND active=1" if active_only else ""), (_bot(bot_key), str(user_id)))


def get_user_habits(user_id, active_only=False, *, bot_key=None):
    return db_run(get_user_habits_async(user_id, active_only, bot_key=bot_key))


async def get_habit_async(habit_id, user_id, *, bot_key=None):
    """Require both the authenticated owner and the active Bot Profile."""
    return await fetch_one("habits", "id=? AND user_id=? AND bot_key=?", (habit_id, str(user_id), _bot(bot_key)))


def get_habit(habit_id, user_id, *, bot_key=None):
    return db_run(get_habit_async(habit_id, user_id, bot_key=bot_key))


async def update_habit_async(habit_id, user_id, *, bot_key=None, **changes):
    allowed = {"title", "category", "description", "repeat_type", "target", "reminder_time", "start_date", "active"}
    changes = {k: v for k, v in changes.items() if k in allowed}
    if not changes or not await get_habit_async(habit_id, user_id, bot_key=bot_key):
        return False
    sets = ",".join(f"{k}=?" for k in changes)
    # Owner predicate must also be enforced by the mutation, not only the read.
    await execute(f"UPDATE habits SET {sets} WHERE id=? AND user_id=? AND bot_key=?", (*changes.values(), habit_id, str(user_id), _bot(bot_key)))
    return True


def update_habit(habit_id, user_id, **changes):
    return db_run(update_habit_async(habit_id, user_id, **changes))


async def delete_habit_async(habit_id, user_id, *, bot_key=None):
    if not await get_habit_async(habit_id, user_id, bot_key=bot_key):
        return False
    await execute("DELETE FROM habits WHERE id=? AND user_id=? AND bot_key=?", (habit_id, str(user_id), _bot(bot_key)))
    return True


def delete_habit(habit_id, user_id):
    return db_run(delete_habit_async(habit_id, user_id))


async def mark_done_async(habit_id, user_id, day=None, *, bot_key=None):
    if not await get_habit_async(habit_id, user_id, bot_key=bot_key):
        return False
    day = day or date.today().isoformat()
    try:
        # Atomic ownership condition: stale or forged callback IDs cannot
        # create cross-user completion rows, even if the habit is deleted.
        row = await execute_returning_one(
            """INSERT INTO habit_logs(habit_id,user_id,done_date,done_at)
               SELECT id,user_id,?,? FROM habits WHERE id=? AND user_id=? AND bot_key=?
               RETURNING id""",
            (day, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), habit_id, str(user_id), _bot(bot_key)),
        )
        return row is not None
    except sqlite3.IntegrityError:
        return False


def mark_done(habit_id, user_id, day=None):
    return db_run(mark_done_async(habit_id, user_id, day))


async def get_logs_async(user_id, habit_id=None, *, bot_key=None):
    """Owner and Bot Profile are mandatory for log retrieval."""
    where = "user_id=? AND habit_id IN (SELECT id FROM habits WHERE user_id=? AND bot_key=?)"
    params = [str(user_id), str(user_id), _bot(bot_key)]
    if habit_id is not None:
        where += " AND habit_id=?"
        params.append(habit_id)
    return await fetch_all("habit_logs", where, params)


def get_logs(user_id, habit_id=None, *, bot_key=None):
    return db_run(get_logs_async(user_id, habit_id, bot_key=bot_key))


async def stats_for_habit_async(habit, user_id, *, bot_key=None):
    if not isinstance(habit, dict) or not await get_habit_async(habit.get("id"), user_id, bot_key=bot_key):
        raise PermissionError("habit_access_denied")
    logs = await get_logs_async(user_id=user_id, habit_id=habit.get("id"), bot_key=bot_key)
    days = sorted({x.get("done_date") for x in logs if x.get("done_date")}, reverse=True)
    today = date.today()
    cur = 0
    cursor = today
    if today.isoformat() not in days:
        cursor = today - timedelta(days=1)
    values = set(days)
    while cursor.isoformat() in values:
        cur += 1
        cursor -= timedelta(days=1)
    best = run = 0
    prev = None
    for value in sorted(values):
        d = datetime.strptime(value, "%Y-%m-%d").date()
        run = run + 1 if prev and d == prev + timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return {"current": cur, "best": best, "total": len(logs), "last": max(days) if days else "—"}


def stats_for_habit(habit, user_id, *, bot_key=None):
    return db_run(stats_for_habit_async(habit, user_id, bot_key=bot_key))


async def get_all_habit_user_ids_async(*, bot_key=None):
    return sorted({x.get("user_id") for x in await fetch_all("habits", "bot_key=?", (_bot(bot_key),)) if x.get("user_id")})


def get_all_habit_user_ids(*, bot_key=None):
    return db_run(get_all_habit_user_ids_async(bot_key=bot_key))
