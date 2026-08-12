"""Deterministic intelligence layer around the existing AI task parser.

Text and voice transcripts share this layer. Questions remain CHAT; every
non-question must become a task or habit, with conservative habit detection.
"""

import re
from datetime import date, timedelta

from services.groq_service import parse_task_request


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_user_text(text: str) -> str:
    text = (text or "").translate(_PERSIAN_DIGITS)
    text = text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = text.replace("ـ", "")
    text = re.sub(r"[\u200c\u200d]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _date_from_language(text: str, today: date) -> str | None:
    patterns = [
        (r"\bپس\s*فردا\b", today + timedelta(days=2)),
        (r"\bفردا\b", today + timedelta(days=1)),
        (r"\bامروز\b", today),
        (r"\bامشب\b", today),
    ]
    for pattern, value in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return value.isoformat()
    return None


def _time_from_language(text: str) -> str | None:
    match = re.search(
        r"(?:ساعت\s*)?(\d{1,2})(?:[:٫.](\d{1,2}))\s*(صبح|ظهر|بعدازظهر|عصر|شب)?|"
        r"\bساعت\s*(\d{1,2})\s*(صبح|ظهر|بعدازظهر|عصر|شب)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    if match.group(1) is not None:
        hour, minute, period = int(match.group(1)), int(match.group(2) or 0), match.group(3) or ""
    else:
        hour, minute, period = int(match.group(4)), 0, match.group(5) or ""
    if hour > 23 or minute > 59:
        return None
    if period in {"بعدازظهر", "عصر", "شب", "ظهر"} and hour < 12:
        hour += 12
    elif period == "صبح" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _looks_like_habit(text: str) -> bool:
    patterns = (
        r"هر\s*روز", r"هر\s*صبح", r"هر\s*شب", r"هر\s*هفته", r"هر\s*ماه",
        r"هفته\s*ای\s*\d+\s*بار", r"روزی\s*\d+\s*بار", r"چند\s*بار\s*در\s*روز",
        r"به\s*صورت\s*منظم", r"مرتب(?:اً)?", r"همیشه",
        r"every\s+day", r"every\s+week", r"every\s+month",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if re.search(r"[؟?]$", stripped):
        return True
    return bool(re.search(
        r"^(?:چی|چه|چطور|چگونه|کدام|کی|چرا|آیا|میشه|می\s*شه|میتونی|می\s*تونی|لطفاً\s*بگو|بگو)\b",
        stripped,
        flags=re.IGNORECASE,
    ))


def _looks_like_explicit_action(text: str) -> bool:
    patterns = (
        r"ثبت\s*(?:کن|کنم|شود)", r"اضافه\s*(?:کن|کنم)", r"ایجاد\s*(?:کن|کنم)",
        r"انجام\s*(?:بدم|بدهم|کنم)", r"آماده\s*(?:کنم|کن)", r"ارسال\s*(?:کنم|کن)",
        r"بررسی\s*(?:کنم|کن)", r"تماس\s*(?:بگیرم|بگیر)", r"بخرم", r"خرید", r"پرداخت",
        r"جلسه\s+دارم", r"یادم\s*(?:بنداز|باشد)", r"remind\s+me", r"add\s+task", r"create\s+task",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _enrich(result: dict, text: str) -> dict:
    today = date.today()
    relative_date = _date_from_language(text, today)
    spoken_time = _time_from_language(text)
    is_question = _looks_like_question(text)
    is_habit = _looks_like_habit(text)

    # Hard contract: a question is CHAT. Otherwise it must be a task or habit.
    if is_question:
        result["action"] = "CHAT"
        return result

    if is_habit:
        result["action"] = "CREATE_HABIT"
        if re.search(r"هر\s*هفته|هفته\s*ای\s*\d+\s*بار|every\s+week", text, re.I):
            result["repeat_type"] = "weekly"
        elif re.search(r"هر\s*ماه|every\s+month", text, re.I):
            result["repeat_type"] = "monthly"
        else:
            result["repeat_type"] = "daily"
        result["deadline"] = ""
        if spoken_time and not result.get("reminder_time"):
            result["reminder_time"] = spoken_time
    else:
        # Any non-question that is not an explicit recurring habit is a one-off task.
        result["action"] = "CREATE_TASK"

    if relative_date and result.get("action") == "CREATE_TASK":
        deadline = str(result.get("deadline") or "")
        if not deadline:
            result["deadline"] = relative_date + (f" {spoken_time}" if spoken_time else "")
        elif spoken_time and re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
            result["deadline"] = deadline + f" {spoken_time}"

    if re.search(r"(?:فوری|ضروری|خیلی\s*مهم|اولویت\s*(?:بالا|زیاد)|urgent|asap|high\s*priority)", text, re.I):
        result["priority"] = "high"
    elif re.search(r"(?:مهم|اولویت\s*متوسط|medium\s*priority)", text, re.I):
        if result.get("priority") not in {"high"}:
            result["priority"] = "medium"

    return result


def parse_task_request_smart(user_id: int, request_text: str) -> dict:
    """Parse text from either Telegram text or a speech-to-text transcript."""
    normalized = normalize_user_text(request_text)
    if not normalized:
        raise ValueError("متن درخواست خالی است.")
    result = parse_task_request(user_id, normalized)
    return _enrich(result, normalized)
