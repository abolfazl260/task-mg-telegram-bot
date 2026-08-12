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


_PROCESSING_STATUS_MESSAGES = [
    "🤖 در حال پردازش درخواست…",
    "🤖 در حال استخراج اطلاعات…",
    "🤖 در حال آماده‌سازی نتیجه…",
]


def get_processing_status_messages() -> list[str]:
    """Return short, generic status messages; never expose model reasoning."""
    return list(_PROCESSING_STATUS_MESSAGES)


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
            f"تگ: {task.get('tags') or '—'} | "
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


def _sanitize_rich_answer(text: str) -> str:
    """Keep only a small Telegram-HTML subset and remove model chatter."""
    text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"(?i)<\s*/?\s*(script|style|ul|ol|li|div|span|h[1-6])[^>]*>", "", text)
    text = re.sub(r"(?i)<\s*(b|strong)\s*>", "<b>", text)
    text = re.sub(r"(?i)</\s*(b|strong)\s*>", "</b>", text)
    text = re.sub(r"(?i)<\s*(i|em)\s*>", "<i>", text)
    text = re.sub(r"(?i)</\s*(i|em)\s*>", "</i>", text)
    text = re.sub(r"(?i)<\s*code\s*>", "<code>", text)
    text = re.sub(r"(?i)</\s*code\s*>", "</code>", text)
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:1200]


def ask_task_assistant(user_id: int, question: str) -> str:
    """Answer only from the user's stored task data with short Telegram HTML."""
    context = _task_context(user_id)
    prompt = (
        "تو دستیار مدیریت کارها هستی. فقط و فقط بر اساس داده‌های تسک زیر پاسخ بده. "
        "از دانش عمومی، حدس، پیشنهاد یا ساختن اطلاعات جدید استفاده نکن. "
        "اگر پاسخ دقیق سؤال در داده‌ها وجود ندارد، دقیقاً NO_DATA برگردان. "
        "پاسخ کوتاه باشد؛ حداکثر ۳ بولت یا ۲ جمله. "
        "برای خوانایی می‌توانی فقط از HTML تلگرام <b>، <i> و <code> استفاده کنی و برای بولت از • استفاده کن. "
        "هیچ مقدمه، استدلال، تحلیل داخلی، زنجیره فکر یا عبارت‌هایی مثل «در حال بررسی» ننویس.\n\n"
        f"داده‌های ثبت‌شده کاربر:\n{context}\n\n"
        f"درخواست کاربر:\n{question}"
    )
    answer = _groq_request(prompt).strip()
    if answer.upper() == "NO_DATA":
        return ""
    return _sanitize_rich_answer(answer)


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


def _auto_category_and_tags(request_text: str, result: dict) -> tuple[str, str]:
    """Apply deterministic Persian category/tag enrichment after the model parse."""
    text = request_text.lower().strip()
    category = str(result.get("category") or "").strip()
    existing = str(result.get("tags") or "").strip()

    rules = [
        ("خرید", r"خرید|بخرم|بخر|فروشگاه|سوپرمارکت|سفارش|تخم\s*مرغ|نان|مواد\s*غذایی", ["#خرید"]),
        ("مالی", r"پرداخت|فاکتور|هزینه|پول|بودجه|درآمد|حقوق|مالی|قبض|صورتحساب", ["#مالی"]),
        ("کاری/شغلی", r"جلسه|شرکت|مدیر|پروژه|گزارش|مشتری|قرارداد|کار|اداری|ارسال\s+.*برای\s+مدیر", ["#کاری"]),
        ("شخصی", r"خانواده|خانه|شخصی|دوست|سفر|تفریح|خودم", ["#شخصی"]),
        ("سلامت", r"ورزش|تمرین|آب\s+بخور|دارو|پزشک|سلامت|خواب|پیاده\s*روی", ["#سلامت"]),
    ]

    matched_tags: list[str] = []
    for label, pattern, tags in rules:
        if re.search(pattern, text):
            if not category:
                category = label
            matched_tags.extend(tags)
            break

    semantic_tags = [
        (r"جلسه", "#جلسه"),
        (r"پروژه", "#پروژه"),
        (r"گزارش", "#گزارش"),
        (r"قرارداد", "#قرارداد"),
        (r"پرداخت|فاکتور", "#پرداخت"),
        (r"ورزش|تمرین", "#ورزش"),
        (r"خرید|بخر|تخم\s*مرغ", "#خرید"),
    ]
    for pattern, tag in semantic_tags:
        if re.search(pattern, text) and tag not in matched_tags:
            matched_tags.append(tag)

    existing_tags = [item.strip() for item in re.split(r"[,،\s]+", existing) if item.strip()]
    all_tags = []
    for tag in existing_tags + matched_tags:
        if tag not in all_tags:
            all_tags.append(tag)
    return category[:100], ", ".join(all_tags)[:300]


def _normalize_ai_result(request_text: str, result: dict) -> dict:
    """Apply deterministic safeguards for common Persian intents after the LLM parse."""
    text = request_text.strip()
    lower = text.lower()

    weekly_match = re.search(
        r"(?:هفته(?:‌|\s*)ای|هفتگی|weekly|every\s+week)\s*(\d+)\s*(?:بار|times?)?",
        lower,
    )
    daily_repeat = bool(
        re.search(
            r"(?:هر\s*روز|روزانه|daily|every\s+day|روزی\s*\d+\s*بار|چند\s*بار\s*در\s*روز)",
            lower,
        )
    )
    monthly_repeat = bool(
        re.search(
            r"(?:هر\s*ماه|ماهانه|monthly|every\s+month)\s+(?:انجام|بررسی|بخوان|بخور|ورزش|تمرین|یادآوری|تکرار)",
            lower,
        )
    )

    if weekly_match or daily_repeat or monthly_repeat or re.search(
        r"(?:همیشه|مرتب|به\s*صورت\s*منظم)\s+(?:یادم\s*بنداز|انجام|تکرار)",
        lower,
    ):
        result["action"] = "CREATE_HABIT"
        if weekly_match:
            result["repeat_type"] = "weekly"
            count = weekly_match.group(1)
            if count and not result.get("target"):
                result["target"] = f"{count} بار در هفته"
        elif daily_repeat:
            result["repeat_type"] = "daily"
        elif monthly_repeat:
            result["repeat_type"] = "monthly"

    if re.search(r"گزارش\s+فروش\s+ماهانه|monthly\s+sales\s+report", lower):
        result["action"] = "CREATE_TASK"
        result["repeat_type"] = ""

    if re.search(
        r"(?:اولویت\s*بالا|خیلی\s*مهم|فوری|ضروری|با\s*اولویت\s*زیاد|urgent|asap|high\s*priority)",
        lower,
    ):
        result["priority"] = "high"
    elif re.search(r"(?:اولویت\s*متوسط|نسبتاً\s*مهم|medium\s*priority)", lower):
        result["priority"] = "medium"

    if result.get("action") == "CHAT" and re.search(
        r"(?:ثبت\s*کن|اضافه\s*کن|آماده\s*کنم|ارسال\s*کنم|بخرم|خرید|پرداخت|انجام\s*بدهم|جلسه|دارم)",
        lower,
    ):
        result["action"] = "CREATE_TASK"

    result["category"], result["tags"] = _auto_category_and_tags(request_text, result)
    return result


def parse_task_request(user_id: int, request_text: str) -> dict:
    """Convert natural Persian/English task or habit text into a validated draft."""
    today = datetime.now(timezone.utc).date().isoformat()
    prompt = f"""
تو موتور استخراج درخواست ربات مدیریت کار و عادت هستی.
پیام کاربر را فقط به یک JSON معتبر تبدیل کن. هیچ توضیح، Markdown یا استدلالی خارج از JSON ننویس.

تاریخ امروز میلادی: {today}

عملیات:
- CREATE_TASK: کار یک‌باره، خرید، پرداخت، جلسه، ارسال، آماده‌سازی یا هر کار غیرتکراری.
- CREATE_HABIT: رفتار واقعاً تکرارشونده یا دارای یادآوری تکراری.
- CHAT: فقط سؤال صریح، احوال‌پرسی، مشاوره یا درخواست اطلاعات درباره داده‌های قبلی.

قانون مهم تشخیص:
- «هر هفته سه بار ورزش کنم» = CREATE_HABIT, repeat_type=weekly, target="۳ بار در هفته".
- «هر روز ساعت ۸ ورزش کنم» = CREATE_HABIT, repeat_type=daily, reminder_time="08:00".
- «هر ماه گزارش مالی را بررسی کنم» = CREATE_HABIT, repeat_type=monthly.
- اما «گزارش فروش ماهانه را آماده کنم» = CREATE_TASK؛ «ماهانه» اینجا صفت گزارش است، نه دستور تکرار.
- «پرداخت فاکتور شرکت را برای امروز با اولویت بالا ثبت کن» = CREATE_TASK, priority=high.
- «فردا گزارش پروژه را برای مدیرم ارسال کنم» = CREATE_TASK با موعد فردا.
- «خرید تخم مرغ» = CREATE_TASK.
- هر دستور یا جمله خبری عملیاتی که سؤال نباشد، CREATE_TASK است.

دسته‌بندی خودکار:
- خرید، بخر، فروشگاه، سفارش و مواد غذایی → «خرید»
- شرکت، جلسه، پروژه، مدیر، مشتری، گزارش و قرارداد → «کاری/شغلی»
- پرداخت، فاکتور، هزینه، بودجه و قبض → «مالی»
- خانواده، خانه، سفر و امور فردی → «شخصی»
- ورزش، دارو، پزشک و سلامت → «سلامت»

تگ‌های خودکار مرتبط را نیز استخراج کن؛ مانند #خرید، #پروژه، #جلسه، #گزارش، #پرداخت، #ورزش.
اگر کاربر تگ مشخصی گفته، آن را هم حفظ کن.

قوانین زمان:
- امروز، فردا و پس‌فردا را بر اساس {today} به YYYY-MM-DD تبدیل کن.
- ساعت را HH:MM و در صورت نیاز ۲۴ ساعته بنویس.
- ساعت ۲ بعدازظهر = 14:00.
- برای CREATE_TASK اگر تاریخ/ساعت گفته نشده، deadline خالی باشد؛ حدس نزن.
- برای CREATE_HABIT deadline همیشه خالی است.

قوانین عادت:
- daily: هر روز، روزانه، هر صبح، هر شب، every day, daily.
- weekly: هر هفته، هفتگی، هفته‌ای چند بار، every week, weekly.
- monthly: هر ماه، ماهانه، every month, monthly فقط وقتی نقش تکرار دارد.
- چند بار در روز → daily.
- زمان‌های صریح یادآوری در reminder_time با کاما و بدون فاصله.
- هدف تعداد/مقدار/مدت در target.
- اگر زمان یادآوری گفته نشده، reminder_time خالی باشد.

قوانین اولویت:
- پیش‌فرض low.
- فقط با اشاره صریح به اهمیت/فوریت high یا medium.
- «اولویت بالا»، «فوری»، «ضروری»، «خیلی مهم»، urgent، ASAP → high.

قوانین زبان:
- title، description، category و tags به زبان خود کاربر باشند.
- عنوان کوتاه و واضح باشد.

فقط این JSON را برگردان:
{{
  "action": "CREATE_TASK" یا "CREATE_HABIT" یا "CHAT",
  "title": "عنوان کوتاه",
  "deadline": "YYYY-MM-DD HH:MM" یا "",
  "priority": "high" یا "medium" یا "low",
  "category": "",
  "tags": "",
  "description": "",
  "repeat_type": "daily" یا "weekly" یا "monthly" یا "",
  "target": "",
  "reminder_time": "HH:MM,HH:MM" یا ""
}}

پیام کاربر:
{request_text}
"""

    result = _normalize_ai_result(request_text, _extract_json(_groq_request(prompt)))

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
            raise GroqRequestError("نوع تکرار عادت مشخص نیست. لطفاً روزانه، هفتگی یا ماهانه بودن آن را مشخص کنید.")
    else:
        repeat_type = ""

    reminder_time = str(result.get("reminder_time") or "").strip()
    if reminder_time:
        times = [item.strip() for item in reminder_time.split(",") if item.strip()]
        valid_times = [item for item in times if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item)]
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
