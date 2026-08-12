"""Groq-powered task and habit assistant helpers."""

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL
from services.task_service import get_all_user_tasks


logger = logging.getLogger(__name__)


class GroqConfigurationError(RuntimeError):
    """Raised when Groq integration is not configured."""


class GroqRequestError(RuntimeError):
    """Raised when Groq returns an unusable response."""


def _task_context(user_id: int, limit: int = 25) -> str:
    tasks = get_all_user_tasks(user_id)
    if not tasks:
        return "هنوز تسکی برای این کاربر ثبت نشده است."
    priority_order = {"high": 0, "medium": 1, "low": 2}
    status_order = {"pending": 0, "in_progress": 1, "done": 2, "cancelled": 3}
    tasks = sorted(tasks, key=lambda task: (
        status_order.get(task.get("status"), 9),
        priority_order.get(task.get("priority"), 9),
        task.get("deadline") or "9999-99-99",
    ))[:limit]
    lines = []
    for index, task in enumerate(tasks, start=1):
        lines.append(
            f"{index}. عنوان: {task.get('title') or '—'} | "
            f"وضعیت: {task.get('status') or 'pending'} | "
            f"اولویت: {task.get('priority') or 'low'} | "
            f"ددلاین: {task.get('deadline') or 'ندارد'} | "
            f"دسته: {task.get('category') or '—'} | "
            f"توضیح: {(task.get('description') or '—')[:120]}"
        )
    return "\n".join(lines)


def _extract_text(payload: dict) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            value = content.get("text")
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    return "\n".join(parts).strip()


def _groq_request(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise GroqConfigurationError("GROQ_API_KEY تنظیم نشده است.")
    body = json.dumps({"model": GROQ_MODEL, "input": prompt}).encode("utf-8")
    request = urllib.request.Request(
        GROQ_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "task-mg-telegram-bot/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:500]
        logger.warning("groq_http_error status=%s detail=%s", exc.code, detail)
        raise GroqRequestError("پاسخ مناسبی از Groq دریافت نشد.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("groq_request_failed error=%s", exc)
        raise GroqRequestError("ارتباط با Groq برقرار نشد.") from exc
    text = _extract_text(payload)
    if not text:
        raise GroqRequestError("پاسخ Groq خالی بود.")
    return text


def ask_task_assistant(user_id: int, question: str) -> str:
    """Ask Groq for a concise Persian answer based on the user's tasks."""
    prompt = (
        "تو دستیار فارسی مدیریت کارها هستی. فقط بر اساس تسک‌های زیر پاسخ بده؛ "
        "اگر داده کافی نیست شفاف بگو. پاسخ را کوتاه، عملیاتی و بولت‌دار بنویس.\n\n"
        f"تسک‌ها:\n{_task_context(user_id)}\n\n"
        f"سؤال کاربر:\n{question}"
    )
    return _groq_request(prompt)[:3500]


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise GroqRequestError("پاسخ ساختاریافته هوش مصنوعی قابل پردازش نبود.")
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise GroqRequestError("پاسخ ساختاریافته هوش مصنوعی قابل پردازش نبود.") from exc
    if not isinstance(value, dict):
        raise GroqRequestError("پاسخ ساختاریافته هوش مصنوعی نامعتبر است.")
    return value


def parse_task_request(user_id: int, request_text: str) -> dict:
    """Convert natural Persian task/habit text into a validated draft."""
    today = datetime.now(timezone.utc).date().isoformat()
    prompt = f"""
تو موتور استخراج درخواست برای یک ربات مدیریت کار و عادت فارسی هستی.
تاریخ امروز میلادی: {today}

پیام کاربر را تحلیل کن و فقط JSON معتبر برگردان، بدون Markdown و بدون توضیح.
سه حالت ممکن است:
- CREATE_TASK: یک کار یک‌باره یا دارای موعد مشخص.
- CREATE_HABIT: یک رفتار/کار تکرارشونده که باید به عنوان عادت ذخیره شود و در صورت وجود زمان، یادآوری شود.
- CHAT: سؤال، مشاوره یا درخواست غیرعملیاتی.

ساختار دقیق JSON:
{{
  "action": "CREATE_TASK" یا "CREATE_HABIT" یا "CHAT",
  "title": "عنوان کوتاه و روشن",
  "deadline": "YYYY-MM-DD HH:MM" یا "",
  "priority": "high" یا "medium" یا "low",
  "category": "" یا دسته‌ای که صریحاً در پیام آمده,
  "tags": "" یا تگ‌هایی که صریحاً در پیام آمده,
  "description": "اطلاعات تکمیلی پیام",
  "repeat_type": "daily" یا "weekly" یا "monthly" یا "",
  "target": "هدف/مقدار عادت یا خالی",
  "reminder_time": "HH:MM,HH:MM" یا ""
}}

قواعد مهم:
- اگر کاربر از تکرار یا روال استفاده کرد، مثل «هر روز»، «روزانه»، «هر هفته»، «هفته‌ای»، «هر ماه»، «به صورت منظم»، «همیشه یادم بنداز»، «هر شب»، «هر صبح»، یا انجام چندباره در روز، action=CREATE_HABIT است.
- اگر کار فقط یک بار برای یک تاریخ/ساعت مشخص است، action=CREATE_TASK است.
- اگر کاربر برای یک رفتار تکرارشونده ساعت مشخص خواست، آن ساعت را در reminder_time قرار بده.
- اگر چند ساعت در روز گفته شد، همه را با کاما در reminder_time قرار بده؛ نمونه: «هر روز ساعت ۸ و ۱۴ آب بخورم» → «08:00,14:00».
- «هر روز» → repeat_type=daily، «هر هفته/هفتگی» → weekly، «هر ماه/ماهانه» → monthly.
- برای عباراتی مثل «هر صبح» یا «هر شب»، repeat_type=daily است؛ اگر ساعت دقیق داده نشده، reminder_time خالی بماند و زمان را حدس نزن.
- اگر تکرار وجود دارد ولی ساعت ندارد، habit ساخته شود بدون یادآوری؛ کاربر بعداً می‌تواند یادآوری را تنظیم کند.
- «چند بار در روز» به معنی عادت است؛ اگر تعداد و ساعت‌ها مشخص نیست، target را نگه دار و reminder_time را حدس نزن.
- «هفته‌ای سه بار» را فعلاً به عنوان habit با repeat_type=weekly استخراج کن و عبارت «سه بار» را در target/description حفظ کن؛ ساختار فعلی دیتابیس فقط روزانه/هفتگی/ماهانه را پشتیبانی می‌کند و نباید Schema جدیدی پیشنهاد شود.
- «امروز ساعت ۲» یعنی امروز ساعت 14:00، مگر اینکه متن صریحاً 2 صبح را بگوید.
- «ساعت ۱۴» یعنی 14:00.
- «فردا» و «پس‌فردا» را با توجه به تاریخ امروز به تاریخ میلادی تبدیل کن.
- اگر ساعت یا تاریخ گفته نشده، deadline خالی باشد.
- زمان یا جزئیاتی که در پیام نیست را حدس نزن.
- priority پیش‌فرض medium است.
- title را از نیت اصلی بساز، نه از کل جمله.
- نام شرکت، شخص یا مکان را در title حفظ کن.
- برای عادت، deadline را خالی بگذار و از repeat_type/reminder_time استفاده کن.
- اگر پیام صرفاً سؤال یا درخواست مشاوره است، action=CHAT باشد.

پیام کاربر:
{request_text}
"""
    result = _extract_json(_groq_request(prompt))
    action = str(result.get("action") or "CHAT").upper()
    if action not in {"CREATE_TASK", "CREATE_HABIT"}:
        return {"action": "CHAT"}

    title = str(result.get("title") or "").strip()
    if not title:
        raise GroqRequestError("عنوان از پیام شما قابل تشخیص نبود.")
    priority = str(result.get("priority") or "medium").lower()
    if priority not in {"high", "medium", "low"}:
        priority = "medium"
    deadline = str(result.get("deadline") or "").strip()
    if deadline and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?", deadline):
        deadline = ""
    repeat_type = str(result.get("repeat_type") or "").lower()
    if repeat_type not in {"daily", "weekly", "monthly"}:
        repeat_type = "daily" if action == "CREATE_HABIT" else ""
    reminder_time = str(result.get("reminder_time") or "").strip()
    if reminder_time:
        times = [item.strip() for item in reminder_time.split(",") if item.strip()]
        times = [item for item in times if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item)]
        reminder_time = ",".join(times)
    return {
        "action": action,
        "title": title[:200],
        "deadline": "" if action == "CREATE_HABIT" else deadline,
        "priority": priority,
        "category": str(result.get("category") or "").strip()[:100],
        "tags": str(result.get("tags") or "").strip()[:300],
        "description": str(result.get("description") or "").strip()[:2000],
        "repeat_type": repeat_type,
        "target": str(result.get("target") or "").strip()[:200],
        "reminder_time": reminder_time,
    }
