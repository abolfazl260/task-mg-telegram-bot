import uuid
from datetime import date, datetime, timedelta, timezone
import sqlite3
from services.database import sync_all, sync_one, sync_execute

# قالب‌های آماده عمداً ثابت و داخل کد نگهداری می‌شوند؛ جدول جدیدی لازم نیست.
TEMPLATES = [
    {
        "key": "water",
        "title": "💧 نوشیدن آب",
        "target_value": 5,
        "target_unit": "بار در روز",
        "kind": "تعداد دفعات",
        "target": "۵ بار در روز",
        "repeat_type": "daily",
        "reminder_times": ["08:00", "11:00", "14:00", "17:00", "20:00"],
        "reminder_time": "08:00,11:00,14:00,17:00,20:00",
        "category": "سلامت",
        "description": "هدف ۵ بار در روز؛ یادآوری‌ها از ساعت ۸ صبح و در ساعت‌های مختلف روز.",
    },
    {
        "key": "medicine",
        "title": "💊 یادآوری قرص",
        "target_value": 2,
        "target_unit": "بار در روز",
        "kind": "زمان‌بندی‌شده",
        "target": "۲ بار در روز",
        "repeat_type": "daily",
        "reminder_times": ["09:00", "21:00"],
        "reminder_time": "09:00,21:00",
        "category": "سلامت",
        "description": "دو یادآوری روزانه در ساعت ۹ صبح و ۹ شب.",
    },
    {
        "key": "meditation",
        "title": "🧘 مدیتیشن",
        "target_value": 20,
        "target_unit": "دقیقه",
        "kind": "مدت زمان",
        "target": "۲۰ دقیقه",
        "repeat_type": "daily",
        "reminder_times": [],
        "reminder_time": "",
        "category": "سلامت",
        "description": "۲۰ دقیقه مدیتیشن در روز.",
    },
    {
        "key": "reading",
        "title": "📚 مطالعه کتاب",
        "target_value": 30,
        "target_unit": "دقیقه",
        "kind": "مدت زمان",
        "target": "۳۰ دقیقه",
        "repeat_type": "daily",
        "reminder_times": [],
        "reminder_time": "",
        "category": "یادگیری",
        "description": "۳۰ دقیقه مطالعه کتاب در روز.",
    },
    {
        "key": "gym",
        "title": "🏋️ باشگاه",
        "target_value": 30,
        "target_unit": "دقیقه",
        "kind": "مدت زمان",
        "target": "۳۰ دقیقه",
        "repeat_type": "daily",
        "reminder_times": [],
        "reminder_time": "",
        "category": "سلامت",
        "description": "۳۰ دقیقه فعالیت در باشگاه در روز.",
    },
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


def init_habits():
    from services.database import _run, init_db
    _run(init_db())


def _ensure_user(user_id):
    uid = str(user_id)
    if not sync_one("users", "user_id=?", (uid,)):
        sync_execute(
            "INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)",
            (uid, "UTC", "jalali"),
        )


def create_habit(user_id, title, category="", description="", repeat_type="daily", target="", reminder_time="", start_date=""):
    _ensure_user(user_id)
    hid = str(uuid.uuid4())[:8]
    sync_execute(
        """INSERT INTO habits(
            id,user_id,title,category,description,repeat_type,target,reminder_time,start_date,active,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            hid,
            str(user_id),
            title,
            category or "",
            description or "",
            repeat_type,
            target or "",
            reminder_time or "",
            start_date or date.today().isoformat(),
            1,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ),
    )
    return hid


def get_user_habits(user_id, active_only=False):
    return sync_all("habits", "user_id=?" + (" AND active=1" if active_only else ""), (str(user_id),))


def get_habit(habit_id):
    return sync_one("habits", "id=?", (habit_id,))


def update_habit(habit_id, **changes):
    allowed = {"title", "category", "description", "repeat_type", "target", "reminder_time", "start_date", "active"}
    changes = {k: v for k, v in changes.items() if k in allowed}
    if not changes or not get_habit(habit_id):
        return False
    sets = ",".join(f"{k}=?" for k in changes)
    sync_execute(f"UPDATE habits SET {sets} WHERE id=?", (*changes.values(), habit_id))
    return True


def delete_habit(habit_id):
    if not get_habit(habit_id):
        return False
    sync_execute("DELETE FROM habits WHERE id=?", (habit_id,))
    return True


def mark_done(habit_id, user_id, day=None):
    """Idempotent under concurrent requests; the UNIQUE constraint is authoritative."""
    day = day or date.today().isoformat()
    _ensure_user(user_id)
    try:
        sync_execute(
            "INSERT INTO habit_logs(habit_id,user_id,done_date,done_at) VALUES(?,?,?,?)",
            (habit_id, str(user_id), day, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def get_logs(user_id=None, habit_id=None):
    where = []
    params = []
    if user_id is not None:
        where.append("user_id=?")
        params.append(str(user_id))
    if habit_id is not None:
        where.append("habit_id=?")
        params.append(habit_id)
    return sync_all("habit_logs", " AND ".join(where) if where else "", params)


def stats_for_habit(habit):
    logs = get_logs(habit_id=habit.get("id"))
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


def get_all_habit_user_ids():
    return sorted({x.get("user_id") for x in sync_all("habits") if x.get("user_id")})
