"""Deterministic intelligence layer around the existing AI task parser.

The LLM remains responsible for semantic extraction. This layer normalizes common
Persian input variants and applies conservative safeguards so text and voice
transcripts are interpreted consistently without duplicating task business logic.
"""

import re
from datetime import date, timedelta

from services.groq_service import parse_task_request


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_user_text(text: str) -> str:
    """Normalize common Persian/Arabic Unicode and spacing variants."""
    text = (text or "").translate(_PERSIAN_DIGITS)
    text = text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = text.replace("ـ", "")
    text = re.sub(r"[\u200c\u200d]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _date_from_language(text: str, today: date) -> str | None:
    """Resolve unambiguous relative Persian dates without guessing."""
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
    """Extract common Persian spoken/written clock expressions."""
    match = re.search(r"\b(\d{1,2})(?:[:٫.](\d{1,2}))?\s*(صبح|ظهر|بعدازظهر|عصر|شب)?\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    period = match.group(3) or ""
    if hour > 23 or minute > 59:
        return None
    if period in {"بعدازظهر", "عصر", "شب"} and hour < 12:
        hour += 12
    elif period == "ظهر" and hour < 12:
        hour += 12
    elif period == "صبح" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _looks_like_habit(text: str) -> bool:
    patterns = (
        r"هر\s*روز", r"روزانه", r"هر\s*صبح", r"هر\s*شب", r"هر\s*صبح", r"هر\s*شب",
        r"هر\s*هفته", r"هفتگی", r"هفته\s*ای", r"هر\s*ماه", r"ماهانه",
        r"روزی\s*\d+\s*بار", r"چند\s*بار\s*در\s*روز", r"به\s*صورت\s*منظم",
        r"مرتب(?:اً)?", r"همیشه", r"every\s+day", r"daily", r"every\s+week",
        r"weekly", r"every\s+month", r"monthly",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_question(text: str) -> bool:
    return bool(re.search(r"[؟?]$|^(چی|چه|چطور|چگونه|کدام|کی|چرا|آیا)\b", text))


def _looks_like_action(text: str) -> bool:
    patterns = (
        r"ثبت\s*(?:کن|کنم|شود)", r"اضافه\s*(?:کن|کنم)", r"ایجاد\s*(?:کن|کنم)",
        r"انجام\s*(?:بدم|بدهم|کنم)", r"آماده\s*(?:کنم|کن)", r"ارسال\s*(?:کنم|کن)",
        r"بررسی\s*(?:کنم|کن)", r"تماس\s*(?:بگیرم|بگیر)", r"بخرم", r"خرید", r"پرداخت",
        r"جلسه\s+دارم", r"یادم\s*(?:بنداز|باشد)", r"remind\s+me", r"add\s+task", r"create\s+task",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _enrich(result: dict, text: str) -> dict:
    """Conservatively repair fields only when the user explicitly supplied evidence."""
    today = date.today()
    relative_date = _date_from_language(text, today)
    spoken_time = _time_from_language(text)

    if _looks_like_habit(text):
        result["action"] = "CREATE_HABIT"
        if re.search(r"هر\s*هفته|هفتگی|هفته\s*ای|every\s+week|weekly", text, re.I):
            result["repeat_type"] = "weekly"
        elif re.search(r"هر\s*ماه|ماهانه|every\s+month|monthly", text, re.I):
            result["repeat_type"] = "monthly"
        else:
            result["repeat_type"] = "daily"
        result["deadline"] = ""
        if spoken_time and not result.get("reminder_time"):
            result["reminder_time"] = spoken_time

    if not _looks_like_question(text) and _looks_like_action(text):
        result["action"] = "CREATE_HABIT" if _looks_like_habit(text) else "CREATE_TASK"

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
    if result.get("action") == "CHAT":
        if _looks_like_action(normalized) and not _looks_like_question(normalized):
            result["action"] = "CREATE_TASK"
    return _enrich(result, normalized)
