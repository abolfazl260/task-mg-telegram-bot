import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FILE_PATH = "data/users.csv"
HEADERS = [
    "user_id",
    "full_name",
    "username",
    "timezone",
    "date_format",
    "first_seen",
    "last_seen",
    "messages_count",
]
DEFAULT_TIMEZONE = "UTC"
DEFAULT_DATE_FORMAT = "jalali"


def init_users():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(HEADERS)
        return
    rows = read_users()
    _write_all(rows)


def read_users():
    if not os.path.exists(FILE_PATH):
        return []
    with open(FILE_PATH, "r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for h in HEADERS:
            row.setdefault(h, "")
        if not row.get("date_format"):
            row["date_format"] = DEFAULT_DATE_FORMAT
    return rows


def _write_all(rows):
    os.makedirs(os.path.dirname(FILE_PATH) or ".", exist_ok=True)
    with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in HEADERS})


def validate_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo((tz_name or "").strip())
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def record_user(user, increment_usage=True):
    if not user:
        return False
    rows = read_users()
    uid = str(user.id)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for row in rows:
        if row.get("user_id") == uid:
            row["full_name"] = user.full_name or ""
            row["username"] = user.username or ""
            row["last_seen"] = now
            row.setdefault("date_format", DEFAULT_DATE_FORMAT)
            if not row.get("date_format"):
                row["date_format"] = DEFAULT_DATE_FORMAT
            if increment_usage:
                row["messages_count"] = str(int(row.get("messages_count") or 0) + 1)
            _write_all(rows)
            return False
    rows.append({
        "user_id": uid,
        "full_name": user.full_name or "",
        "username": user.username or "",
        "timezone": DEFAULT_TIMEZONE,
        "date_format": DEFAULT_DATE_FORMAT,
        "first_seen": now,
        "last_seen": now,
        "messages_count": "1" if increment_usage else "0",
    })
    _write_all(rows)
    return True


def set_user_timezone(user_id, tz_name: str) -> bool:
    tz_name = (tz_name or "").strip()
    if not validate_timezone(tz_name):
        return False
    rows = read_users()
    uid = str(user_id)
    found = False
    for row in rows:
        if row.get("user_id") == uid:
            row["timezone"] = tz_name
            row.setdefault("date_format", DEFAULT_DATE_FORMAT)
            found = True
            break
    if not found:
        rows.append({
            "user_id": uid,
            "timezone": tz_name,
            "date_format": DEFAULT_DATE_FORMAT,
            "messages_count": "0",
        })
    _write_all(rows)
    return True


def get_user_timezone(user_id) -> str:
    for row in read_users():
        if row.get("user_id") == str(user_id):
            return row.get("timezone") or DEFAULT_TIMEZONE
    return DEFAULT_TIMEZONE


def set_user_date_format(user_id, date_format: str) -> bool:
    date_format = (date_format or "").strip().lower()
    if date_format not in {"jalali", "gregorian"}:
        return False
    rows = read_users()
    uid = str(user_id)
    found = False
    for row in rows:
        if row.get("user_id") == uid:
            row["date_format"] = date_format
            found = True
            break
    if not found:
        rows.append({
            "user_id": uid,
            "date_format": date_format,
            "timezone": DEFAULT_TIMEZONE,
            "messages_count": "0",
        })
    _write_all(rows)
    return True


def get_user_date_format(user_id) -> str:
    for row in read_users():
        if row.get("user_id") == str(user_id):
            value = (row.get("date_format") or DEFAULT_DATE_FORMAT).strip().lower()
            return value if value in {"jalali", "gregorian"} else DEFAULT_DATE_FORMAT
    return DEFAULT_DATE_FORMAT


def all_users():
    return read_users()
