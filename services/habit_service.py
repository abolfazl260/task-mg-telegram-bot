import csv
import os
import uuid
from datetime import date, datetime, timedelta

HABITS_PATH = "data/habits.csv"
LOGS_PATH = "data/habit_logs.csv"

HABIT_HEADERS = [
    "id", "user_id", "title", "category", "description", "repeat_type",
    "target", "reminder_time", "start_date", "active", "created_at",
]
LOG_HEADERS = ["habit_id", "user_id", "done_date", "done_at"]

TEMPLATES = [
    {"key": "exercise", "title": "🏃 ورزش روزانه", "category": "سلامت", "target": "۳۰ دقیقه ورزش", "description": ""},
    {"key": "water", "title": "💧 نوشیدن آب", "category": "سلامت", "target": "۸ لیوان آب در روز", "description": ""},
    {"key": "sleep", "title": "😴 خواب منظم", "category": "سلامت", "target": "۷ ساعت خواب", "description": ""},
    {"key": "book", "title": "📚 مطالعه کتاب", "category": "یادگیری", "target": "۳۰ دقیقه مطالعه روزانه", "description": ""},
    {"key": "language", "title": "🗣 یادگیری زبان", "category": "یادگیری", "target": "۲۰ دقیقه تمرین", "description": ""},
    {"key": "plan", "title": "📝 برنامه‌ریزی روزانه", "category": "بهره‌وری", "target": "نوشتن برنامه روز", "description": ""},
    {"key": "email", "title": "📧 بررسی ایمیل", "category": "بهره‌وری", "target": "یک بار در روز", "description": ""},
    {"key": "meditation", "title": "🧘 مدیتیشن", "category": "سلامت ذهن", "target": "۱۰ دقیقه در روز", "description": ""},
    {"key": "journal", "title": "📔 ثبت ژورنال روزانه", "category": "سلامت ذهن", "target": "نوشتن تجربیات روزانه", "description": ""},
]


def _ensure(path, headers):
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)
        return
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if any(h not in fields for h in headers):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({h: row.get(h, "") for h in headers})


def init_habits():
    _ensure(HABITS_PATH, HABIT_HEADERS)
    _ensure(LOGS_PATH, LOG_HEADERS)


def _read(path, headers):
    init_habits()
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for h in headers:
            row.setdefault(h, "")
    return rows


def _write(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def create_habit(user_id, title, category="", description="", repeat_type="daily", target="", reminder_time="", start_date=""):
    init_habits()
    habit_id = str(uuid.uuid4())[:8]
    row = {
        "id": habit_id, "user_id": str(user_id), "title": title, "category": category,
        "description": description, "repeat_type": repeat_type, "target": target,
        "reminder_time": reminder_time, "start_date": start_date or date.today().isoformat(),
        "active": "1", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(HABITS_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=HABIT_HEADERS).writerow(row)
    return habit_id


def get_user_habits(user_id, active_only=False):
    rows = [h for h in _read(HABITS_PATH, HABIT_HEADERS) if h.get("user_id") == str(user_id)]
    if active_only:
        rows = [h for h in rows if h.get("active") == "1"]
    return rows


def get_habit(habit_id):
    return next((h for h in _read(HABITS_PATH, HABIT_HEADERS) if h.get("id") == habit_id), None)


def update_habit(habit_id, **changes):
    habits = _read(HABITS_PATH, HABIT_HEADERS)
    ok = False
    for habit in habits:
        if habit.get("id") == habit_id:
            for k, v in changes.items():
                if k in HABIT_HEADERS:
                    habit[k] = v
            ok = True
            break
    if ok:
        _write(HABITS_PATH, HABIT_HEADERS, habits)
    return ok


def delete_habit(habit_id):
    habits = _read(HABITS_PATH, HABIT_HEADERS)
    kept = [h for h in habits if h.get("id") != habit_id]
    if len(kept) == len(habits):
        return False
    _write(HABITS_PATH, HABIT_HEADERS, kept)
    logs = [l for l in _read(LOGS_PATH, LOG_HEADERS) if l.get("habit_id") != habit_id]
    _write(LOGS_PATH, LOG_HEADERS, logs)
    return True


def mark_done(habit_id, user_id, day=None):
    day = day or date.today().isoformat()
    logs = _read(LOGS_PATH, LOG_HEADERS)
    if any(l.get("habit_id") == habit_id and l.get("user_id") == str(user_id) and l.get("done_date") == day for l in logs):
        return False
    with open(LOGS_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([habit_id, str(user_id), day, datetime.now().strftime("%Y-%m-%d %H:%M")])
    return True


def get_logs(user_id=None, habit_id=None):
    logs = _read(LOGS_PATH, LOG_HEADERS)
    if user_id is not None:
        logs = [l for l in logs if l.get("user_id") == str(user_id)]
    if habit_id is not None:
        logs = [l for l in logs if l.get("habit_id") == habit_id]
    return logs


def stats_for_habit(habit):
    logs = get_logs(habit_id=habit.get("id"))
    days = sorted({l.get("done_date") for l in logs if l.get("done_date")}, reverse=True)
    today = date.today()
    current = 0
    cursor = today
    if today.isoformat() not in days:
        cursor = today - timedelta(days=1)
    day_set = set(days)
    while cursor.isoformat() in day_set:
        current += 1
        cursor -= timedelta(days=1)
    best = run = 0
    previous = None
    for value in sorted(day_set):
        d = datetime.strptime(value, "%Y-%m-%d").date()
        run = run + 1 if previous and d == previous + timedelta(days=1) else 1
        best = max(best, run)
        previous = d
    last = max(days) if days else "—"
    return {"current": current, "best": best, "total": len(logs), "last": last}


def get_all_habit_user_ids():
    return sorted({h.get("user_id") for h in _read(HABITS_PATH, HABIT_HEADERS) if h.get("user_id")})
