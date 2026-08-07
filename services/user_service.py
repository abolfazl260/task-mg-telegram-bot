import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FILE_PATH = "data/users.csv"
HEADERS = ["user_id", "full_name", "username", "timezone", "first_seen", "last_seen", "messages_count"]
DEFAULT_TIMEZONE = "UTC"


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
    return rows


def _write_all(rows):
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
            if increment_usage:
                row["messages_count"] = str(int(row.get("messages_count") or 0) + 1)
            _write_all(rows)
            return False
    rows.append({
        "user_id": uid,
        "full_name": user.full_name or "",
        "username": user.username or "",
        "timezone": DEFAULT_TIMEZONE,
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
            found = True
            break
    if not found:
        rows.append({"user_id": uid, "timezone": tz_name, "messages_count": "0"})
    _write_all(rows)
    return True


def get_user_timezone(user_id) -> str:
    for row in read_users():
        if row.get("user_id") == str(user_id):
            return row.get("timezone") or DEFAULT_TIMEZONE
    return DEFAULT_TIMEZONE


def all_users():
    return read_users()
