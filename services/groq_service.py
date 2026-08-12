"""Groq-powered task assistant helpers."""

import json
import logging
import urllib.error
import urllib.request

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
    tasks = sorted(
        tasks,
        key=lambda task: (
            status_order.get(task.get("status"), 9),
            priority_order.get(task.get("priority"), 9),
            task.get("deadline") or "9999-99-99",
        ),
    )[:limit]

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


def ask_task_assistant(user_id: int, question: str) -> str:
    """Ask Groq for a concise Persian answer based on the user's tasks."""
    if not GROQ_API_KEY:
        raise GroqConfigurationError("GROQ_API_KEY تنظیم نشده است.")

    prompt = (
        "تو دستیار فارسی مدیریت کارها هستی. فقط بر اساس تسک‌های زیر پاسخ بده؛ "
        "اگر داده کافی نیست شفاف بگو. پاسخ را کوتاه، عملیاتی و بولت‌دار بنویس.\n\n"
        f"تسک‌ها:\n{_task_context(user_id)}\n\n"
        f"سؤال کاربر:\n{question}"
    )
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

    answer = _extract_text(payload)
    if not answer:
        raise GroqRequestError("پاسخ Groq خالی بود.")
    return answer[:3500]
