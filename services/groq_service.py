"""Groq-powered task assistant helpers."""

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
    """Convert natural Persian task text into a validated task draft."""
    today = datetime.now(timezone.utc).date().isoformat()
    prompt = f"""
تو موتور استخراج تسک برای یک ربات مدیریت کار فارسی هستی.
تاریخ امروز میلادی: {today}

پیام کاربر را تحلیل کن و فقط JSON معتبر برگردان، بدون Markdown و بدون توضیح.
اگر کاربر قصد ایجاد یک تسک دارد، action برابر CREATE_TASK باشد؛ در غیر این صورت CHAT باشد.
ساختار دقیق:
{{
  "action": "CREATE_TASK" یا "CHAT",
  "title": "عنوان کوتاه و روشن تسک",
  "deadline": "YYYY-MM-DD HH:MM" یا "",
  "priority": "high" یا "medium" یا "low",
  "category": "" یا دسته‌ای که صریحاً در پیام آمده,
  "tags": "" یا تگ‌هایی که صریحاً در پیام آمده,
  "description": "اطلاعات تکمیلی پیام"
}}

قواعد مهم:
- «امروز ساعت ۲» یعنی امروز ساعت 14:00، مگر اینکه متن صریحاً 2 صبح را بگوید.
- «ساعت ۱۴» یعنی 14:00.
- «فردا» و «پس‌فردا» را با توجه به تاریخ امروز به تاریخ میلادی تبدیل کن.
- اگر ساعت یا تاریخ گفته نشده، deadline خالی باشد.
- زمان یا جزئیاتی که در پیام نیست را حدس نزن.
- priority پیش‌فرض medium است.
- title را از نیت اصلی کار بساز، نه از کل جمله.
- نام شرکت، شخص یا مکان را در title حفظ کن.
- اگر پیام صرفاً سؤال یا درخواست مشاوره است، action=CHAT باشد.

پیام کاربر:
{request_text}
"""
    result = _extract_json(_groq_request(prompt))
    action = str(result.get("action") or "CHAT").upper()
    if action != "CREATE_TASK":
        return {"action": "CHAT"}
    title = str(result.get("title") or "").strip()
    if not title:
        raise GroqRequestError("عنوان تسک از پیام شما قابل تشخیص نبود.")
    priority = str(result.get("priority") or "medium").lower()
    if priority not in {"high", "medium", "low"}:
        priority = "medium"
    deadline = str(result.get("deadline") or "").strip()
    if deadline and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?", deadline):
        deadline = ""
    return {
        "action": "CREATE_TASK",
        "title": title[:200],
        "deadline": deadline,
        "priority": priority,
        "category": str(result.get("category") or "").strip()[:100],
        "tags": str(result.get("tags") or "").strip()[:300],
        "description": str(result.get("description") or "").strip()[:2000],
    }
