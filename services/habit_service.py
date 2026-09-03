from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

from services.database import execute, fetch_all, fetch_one, sync_all, sync_execute, sync_one, _run as db_run

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


async def create_habit_async(user_id, title, category="", description="", repeat_type="daily", target="", reminder_time="", start_date=""):
    await _ensure_user_async(user_id)
    hid = str(uuid.uuid4())[:8]
    await execute(
        """INSERT INTO habits(id,user_id,title,category,description,repeat_type,target,reminder_time,start_date,active,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (hid, str(user_id), title, category or "", description or "", repeat_type, target or "", reminder_time or "", start_date or date.today().isoformat(), 1, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
    )
    return hid


def create_habit(*args, **kwargs):
    return db_run(create_habit_async(*args, **kwargs))


async def get_user_habits_async(user_id, active_only=False):
    return await fetch_all("habits", "user_id=?" + (" AND active=1" if active_only else ""), (str(user_id),))


def get_user_habits(user_id, active_only=False):
    return db_run(get_user_habits_async(user_id, active_only))


async def get_habit_async(habit_id):
    return await fetch_one("habits", "id=?", (habit_id,))


def get_habit(habit_id):
    return db_run(get_habit_async(habit_id))


async def update_habit_async(habit_id, **changes):
    allowed = {"title", "category", "description", "repeat_type", "target", "reminder_time", "start_date", "active"}
    changes = {k: v for k, v in changes.items() if k in allowed}
    if not changes or not await get_habit_async(habit_id):
        return False
    sets = ",".join(f"{k}=?" for k in changes)
    await execute(f"UPDATE habits SET {sets} WHERE id=?", (*changes.values(), habit_id))
    return True


def update_habit(habit_id, **changes):
    return db_run(update_habit_async(habit_id, **changes))


async def delete_habit_async(habit_id):
    if not await get_habit_async(habit_id):
        return False
    await execute("DELETE FROM habits WHERE id=?", (habit_id,))
    return True


def delete_habit(habit_id):
    return db_run(delete_habit_async(habit_id))


async def mark_done_async(habit_id, user_id, day=None):
    day = day or date.today().isoformat()
    await _ensure_user_async(user_id)
    try:
        await execute("INSERT INTO habit_logs(habit_id,user_id,done_date,done_at) VALUES(?,?,?,?)", (habit_id, str(user_id), day, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")))
        return True
    except sqlite3.IntegrityError:
        return False


def mark_done(habit_id, user_id, day=None):
    return db_run(mark_done_async(habit_id, user_id, day))


async def get_logs_async(user_id=None, habit_id=None):
    where = []
    params = []
    if user_id is not None:
        where.append("user_id=?")
        params.append(str(user_id))
    if habit_id is not None:
        where.append("habit_id=?")
        params.append(habit_id)
    return await fetch_all("habit_logs", " AND ".join(where) if where else "", params)


def get_logs(user_id=None, habit_id=None):
    return db_run(get_logs_async(user_id, habit_id))


async def stats_for_habit_async(habit):
    logs = await get_logs_async(habit_id=habit.get("id"))
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


def stats_for_habit(habit):
    return db_run(stats_for_habit_async(habit))


async def get_all_habit_user_ids_async():
    return sorted({x.get("user_id") for x in await fetch_all("habits") if x.get("user_id")})


def get_all_habit_user_ids():
    return db_run(get_all_habit_user_ids_async())
