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
    """Convert natural Persian/English task or habit text into a validated draft."""
    today = datetime.now(timezone.utc).date().isoformat()
    prompt = f"""
تو یک موتور هوشمند استخراج درخواست برای ربات مدیریت کار و عادت هستی.
پیام کاربر را تحلیل کن و فقط یک JSON معتبر برگردان؛ هیچ Markdown یا توضیح اضافه‌ای ننویس.

تاریخ امروز میلادی: {today}

━━━━━━━━━━━━━━━━━━━━
۱) تشخیص عملیات
━━━━━━━━━━━━━━━━━━━━

CREATE_TASK:
کار یک‌باره، جلسه، قرار، پروژه یا کاری که قرار نیست منظم تکرار شود.

CREATE_HABIT:
رفتار یا کاری که کاربر می‌خواهد به شکل منظم و تکرارشونده انجام دهد یا برای آن یادآوری تکراری داشته باشد.
نشانه‌ها شامل «هر روز»، «روزانه»، «هر صبح»، «هر شب»، «هر هفته»، «هفتگی»، «هر ماه»، «ماهانه»،
«هفته‌ای چند بار»، «روزی چند بار»، «چند بار در روز»، «مرتب»، «به صورت منظم»، «همیشه یادم بنداز»
و معادل‌های انگلیسی مانند daily, weekly, monthly, every day, every week, regularly هستند.

CHAT:
فقط سؤال صریح، احوال‌پرسی، مشاوره یا درخواست توضیح غیرعملیاتی.

اگر پیام خبری یا دستوری است و سؤال نیست، پیش‌فرض CREATE_TASK است.
اگر نشانه روشن تکرار وجود دارد، CREATE_HABIT بر CREATE_TASK اولویت دارد.

━━━━━━━━━━━━━━━━━━━━
۲) قوانین زبان
━━━━━━━━━━━━━━━━━━━━

مقادیر متنی title، description، category و tags را به همان زبان پیام کاربر تولید کن.
نام شرکت، شخص و مکان را در title حفظ کن.

━━━━━━━━━━━━━━━━━━━━
۳) تاریخ و ساعت
━━━━━━━━━━━━━━━━━━━━

امروز = {today}

امروز، فردا و پس‌فردا را دقیقاً بر اساس این تاریخ به YYYY-MM-DD تبدیل کن.
ساعت همیشه HH:MM باشد.
«ساعت ۲» یا «۲ بعدازظهر» = 14:00 مگر اینکه متن صراحتاً صبح را بگوید.
«ساعت ۱۴» = 14:00.
برای CREATE_TASK اگر تاریخ یا ساعت گفته نشده، deadline خالی باشد و هرگز حدس نزن.
برای CREATE_HABIT، deadline همیشه خالی است.

━━━━━━━━━━━━━━━━━━━━
۴) قوانین عادت و تکرار
━━━━━━━━━━━━━━━━━━━━

daily: هر روز، روزانه، هر صبح، هر شب، every day, daily
weekly: هر هفته، هفتگی، every week, weekly
monthly: هر ماه، ماهانه، every month, monthly

اگر کاربر چند بار در روز را بیان کرد، عادت روزانه است.
مثال: «هر روز ساعت ۸ و ۱۴ آب بخورم» → daily + reminder_time="08:00,14:00"

اگر گفت «هفته‌ای سه بار ورزش کنم» → weekly و target باید مفهوم «سه بار در هفته» را حفظ کند.
اگر گفت «هر ماه گزارش مالی را بررسی کنم» → monthly.

ساختار فعلی فقط daily/weekly/monthly را پشتیبانی می‌کند؛ Schema جدید پیشنهاد یا اختراع نکن.

اگر تکرار مشخص است ولی ساعت مشخص نشده، عادت ایجاد شود و reminder_time خالی بماند.
اگر کاربر ساعت دقیق برای رفتار تکرارشونده داد، آن را در reminder_time قرار بده.
اگر چند ساعت داده شد، همه ساعت‌های معتبر را با کاما و بدون فاصله برگردان.

━━━━━━━━━━━━━━━━━━━━
۵) هدف عادت
━━━━━━━━━━━━━━━━━━━━

تعداد، مقدار یا مدت هدف را در target قرار بده.

«هر روز ۵ لیوان آب بخورم» → target="۵ لیوان در روز"
«هفته‌ای سه بار ورزش کنم» → target="۳ بار در هفته"
«هر روز ۳۰ دقیقه مطالعه کنم» → target="۳۰ دقیقه در روز"

اگر هدف مشخص نشده، target خالی باشد.

━━━━━━━━━━━━━━━━━━━━
۶) یادآوری
━━━━━━━━━━━━━━━━━━━━

reminder_time فقط بر اساس زمان صریح کاربر پر شود.
هرگز ساعت یادآوری را حدس نزن.

━━━━━━━━━━━━━━━━━━━━
۷) اولویت
━━━━━━━━━━━━━━━━━━━━

priority پیش‌فرض low است.
فقط وقتی کاربر صریحاً فوریت یا اهمیت را بیان کند high یا medium انتخاب کن؛ مانند «فوری»، «خیلی مهم»، «ضروری»، «ASAP»، «urgent».
از متن کاربر درباره اهمیت حدس نزن.

━━━━━━━━━━━━━━━━━━━━
۸) عنوان و توضیحات
━━━━━━━━━━━━━━━━━━━━

title کوتاه و واضح و مبتنی بر نیت اصلی باشد.
مثال: «امروز ساعت ۲ جلسه با شرکت مدیران خودرو دارم» → «جلسه با شرکت مدیران خودرو».
اطلاعات تکمیلی در description قرار بگیرد.

━━━━━━━━━━━━━━━━━━━━
۹) خروجی
━━━━━━━━━━━━━━━━━━━━

فقط این JSON را برگردان:
{{
  "action": "CREATE_TASK" یا "CREATE_HABIT" یا "CHAT",
  "title": "عنوان کوتاه",
  "deadline": "YYYY-MM-DD HH:MM" یا "",
  "priority": "high" یا "medium" یا "low",
  "category": "" یا دسته صریح پیام,
  "tags": "" یا تگ صریح پیام,
  "description": "اطلاعات تکمیلی",
  "repeat_type": "daily" یا "weekly" یا "monthly" یا "",
  "target": "هدف/مقدار عادت یا خالی",
  "reminder_time": "HH:MM,HH:MM" یا ""
}}

پیام کاربر:
{request_text}
"""

    result = _extract_json(_groq_request(prompt))

    action = str(result.get("action") or "CREATE_TASK").upper().strip()
    if action not in {"CREATE_TASK", "CREATE_HABIT", "CHAT"}:
        action = "CREATE_TASK"

    if action == "CHAT":
        return {"action": "CHAT"}

    title = str(result.get("title") or "").strip()
    if not title:
        raise GroqRequestError("عنوان از پیام شما قابل تشخیص نبود.")

    priority = str(result.get("priority") or "low").lower().strip()
    if priority not in {"high", "medium", "low"}:
        priority = "low"

    deadline = str(result.get("deadline") or "").strip()
    if deadline and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?", deadline):
        deadline = ""
    if action == "CREATE_HABIT":
        deadline = ""

    repeat_type = str(result.get("repeat_type") or "").lower().strip()
    if action == "CREATE_HABIT":
        if repeat_type not in {"daily", "weekly", "monthly"}:
            raise GroqRequestError(
                "نوع تکرار عادت مشخص نیست. لطفاً روزانه، هفتگی یا ماهانه بودن آن را مشخص کنید."
            )
    else:
        repeat_type = ""

    reminder_time = str(result.get("reminder_time") or "").strip()
    if reminder_time:
        times = [item.strip() for item in reminder_time.split(",") if item.strip()]
        valid_times = [
            item for item in times
            if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item)
        ]
        reminder_time = ",".join(dict.fromkeys(valid_times))
    if action != "CREATE_HABIT":
        reminder_time = ""

    return {
        "action": action,
        "title": title[:200],
        "deadline": deadline,
        "priority": priority,
        "category": str(result.get("category") or "").strip()[:100],
        "tags": str(result.get("tags") or "").strip()[:300],
        "description": str(result.get("description") or "").strip()[:2000],
        "repeat_type": repeat_type,
        "target": str(result.get("target") or "").strip()[:200],
        "reminder_time": reminder_time,
    }
