"""Bulk import tasks from a structured text block.

Format (one task per line after header):

TASKS
title | priority | deadline | category | tags | description
عنوان نمونه | high | 2026-08-20 | کار | تگ1 تگ2 | توضیح کوتاه
...

- priority: high | medium | low  (default medium)
- deadline: YYYY-MM-DD or Jalali YYYY-MM-DD or empty
- Telegram limit ~4096 chars → max ~30-40 tasks per message recommended
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.task_service import create_task
from utils.date_parse import parse_deadline_input

IMPORT_HELP = """📥 **ایمپورت گروهی تسک**

ساختار متن را دقیقاً به این شکل بفرستید:

```
TASKS
عنوان تسک ۱ | high | 2026-08-20 | کار | پروژه | توضیح اختیاری
عنوان تسک ۲ | medium | 1405-05-29 | شخصی |  | 
عنوان تسک ۳ | low |  | مطالعه | کتاب | بدون مهلت
```

📌 قواعد:
• خط اول حتماً `TASKS` باشد
• هر خط = یک تسک
• فیلدها با `|` جدا می‌شوند
• ترتیب: عنوان | اولویت | مهلت | دسته | تگ | توضیح
• اولویت: `high` / `medium` / `low`
• مهلت: میلادی یا شمسی یا خالی
• حداکثر حدود ۳۰–۴۰ تسک در هر پیام

از دکمه‌های زیر یک **نمونه آماده** بگیر، ویرایش کن و بفرست.
"""

GPT_PROMPT = """متن زیر را کپی کن و به ChatGPT بده تا لیست تسک‌هایت را به فرمت درست تبدیل کند:

---
لطفاً لیست کارها / برنامه زیر را به فرمت دقیق زیر تبدیل کن تا بتوانم در ربات تسک‌منیجر تلگرام ایمپورت کنم.

فرمت خروجی (فقط همین، بدون توضیح اضافه):

TASKS
عنوان | اولویت | مهلت | دسته | تگ | توضیح

قواعد:
- اولویت فقط یکی از: high ، medium ، low
- مهلت به صورت YYYY-MM-DD (میلادی) یا خالی
- اگر مهلت شمسی داری خودت به میلادی تبدیل کن
- هر خط یک تسک
- فیلد خالی را خالی بگذار (دو | پشت‌سرهم)
- حداکثر ۳۰ تسک

لیست کارهای من:
[اینجا لیست یا برنامه خودت را بنویس]
---
"""

# Ready-to-paste sample templates for common use cases
SAMPLE_TEMPLATES = {
    "checklist": {
        "title": "✅ چک‌لیست",
        "body": """TASKS
بررسی مدارک | high |  | چک‌لیست | مهم | موارد ضروری را تیک بزن
تماس با مشتری | medium |  | چک‌لیست | پیگیری | 
ارسال ایمیل تأیید | medium |  | چک‌لیست |  | 
آپلود فایل‌ها در درایو | low |  | چک‌لیست |  | 
بازبینی نهایی قبل از تحویل | high |  | چک‌لیست | مهم | 
بستن تسک‌های انجام‌شده | low |  | چک‌لیست |  | """,
    },
    "shopping": {
        "title": "🛒 لیست خرید",
        "body": """TASKS
نان سنگک | medium |  | خرید | نانوایی | ۲ عدد
شیر کم‌چرب | medium |  | خرید | لبنیات | ۱ لیتر
تخم‌مرغ | medium |  | خرید | پروتئین | یک شانه
برنج | low |  | خرید | خشکبار | ۲ کیلو
گوجه‌فرنگی | medium |  | خرید | سبزی | ۱ کیلو
خیار | low |  | خرید | سبزی | 
ماست | medium |  | خرید | لبنیات | 
شوینده ظرف | low |  | خرید | منزل | """,
    },
    "study": {
        "title": "📚 برنامه درسی",
        "body": """TASKS
زیست دوازدهم — فصل مولکول‌های اطلاعاتی | high |  | مطالعه | زیست | صفحه ۱ تا ۱۶
فیزیک دوازدهم — حرکت بر خط راست | high |  | مطالعه | فیزیک | صفحه ۱ تا ۲۶
شیمی دوازدهم — قدردانی از زحمات و کیمیاگران | medium |  | مطالعه | شیمی | صفحه ۱ تا ۲۴
ریاضی دوازدهم — تابع | high |  | مطالعه | ریاضی | صفحه ۱ تا ۴۶
تست زیست — ۲۰ سؤال طبقه‌بندی | medium |  | مطالعه | تست | تحلیل غلط‌ها
مرور خلاصه فیزیک هفته | medium |  | مطالعه | مرور | 
عمومی — فارسی درس ۱ | low |  | مطالعه | عمومی | """,
    },
    "shift": {
        "title": "🍽️ شیفت رستوران",
        "body": """TASKS
شیفت صبح — آماده‌سازی سالن | high |  | شیفت رستوران | صبح | باز کردن، چیدمان میزها
شیفت صبح — کنترل موجودی یخچال | high |  | شیفت رستوران | صبح | گزارش کسری
شیفت ظهر — پذیرش و سالن | medium |  | شیفت رستوران | ظهر | 
شیفت عصر — آشپزخانه کمک‌کار | medium |  | شیفت رستوران | عصر | 
شیفت شب — بستن صندوق | high |  | شیفت رستوران | شب | شمارش و گزارش
شیفت شب — نظافت نهایی سالن و آشپزخانه | high |  | شیفت رستوران | شب | 
تحویل شیفت به نفر بعدی | medium |  | شیفت رستوران |  | موارد باز را بنویس""",
    },
}


def _samples_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نمونه چک‌لیست", callback_data="import_tpl_checklist")],
        [InlineKeyboardButton("🛒 نمونه لیست خرید", callback_data="import_tpl_shopping")],
        [InlineKeyboardButton("📚 نمونه برنامه درسی", callback_data="import_tpl_study")],
        [InlineKeyboardButton("🍽️ نمونه شیفت رستوران", callback_data="import_tpl_shift")],
        [InlineKeyboardButton("📋 پرامپت GPT", callback_data="import_show_prompt")],
        [InlineKeyboardButton("❌ انصراف", callback_data="import_cancel")],
    ])


async def start_import_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help + sample templates and set step for receiving bulk text."""

    context.user_data["step"] = "import_bulk"

    if update.callback_query:
        msg = update.callback_query.message
    else:
        msg = update.message

    await msg.reply_text(
        IMPORT_HELP,
        parse_mode="Markdown",
        reply_markup=_samples_keyboard(),
    )


async def import_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "import_bulk":
        await start_import_flow(update, context)
        return

    if data == "import_show_prompt":
        await query.message.reply_text(
            "📋 پرامپت آماده برای ChatGPT (کپی کن):\n\n" + GPT_PROMPT
        )
        context.user_data["step"] = "import_bulk"
        return

    if data.startswith("import_tpl_"):
        key = data.replace("import_tpl_", "", 1)
        sample = SAMPLE_TEMPLATES.get(key)
        if not sample:
            await query.message.reply_text("نمونه پیدا نشد.")
            return
        context.user_data["step"] = "import_bulk"
        await query.message.reply_text(
            f"📥 نمونه «{sample['title']}»\n\n"
            f"متن زیر را کپی کن، در صورت نیاز ویرایش کن، و همین‌جا بفرست تا ثبت شود:\n\n"
            f"```\n{sample['body']}\n```",
            parse_mode="Markdown",
        )
        # also send plain (easy copy on mobile)
        await query.message.reply_text(sample["body"])
        return

    if data == "import_cancel":
        context.user_data.pop("step", None)
        await query.message.reply_text("ایمپورت لغو شد.")
        return


async def handle_import_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Parse bulk text if step == import_bulk. Return True if handled."""

    if context.user_data.get("step") != "import_bulk":
        return False

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("متن خالی بود.")
        return True

    if text.lower() in ("cancel", "لغو", "انصراف"):
        context.user_data.pop("step", None)
        await update.message.reply_text("ایمپورت لغو شد.")
        return True

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        await update.message.reply_text("متنی پیدا نشد.")
        return True

    start = 0
    if lines[0].upper().startswith("TASKS"):
        start = 1

    data_lines = lines[start:]
    if not data_lines:
        await update.message.reply_text(
            "بعد از خط TASKS هیچ تسکی نبود.\n"
            "از دکمه‌های نمونه استفاده کن یا متن را با فرمت درست بفرست."
        )
        return True

    if len(text) > 4000:
        await update.message.reply_text(
            "⚠️ متن خیلی طولانی است (محدودیت تلگرام).\n"
            "لطفاً حداکثر حدود ۳۰–۴۰ تسک در هر پیام بفرستید."
        )
        return True

    created = []
    errors = []

    for i, line in enumerate(data_lines, start=1):
        if line.startswith("```"):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 1 or not parts[0]:
            errors.append(f"خط {i}: عنوان خالی")
            continue

        title = parts[0][:200]
        priority = (parts[1].lower() if len(parts) > 1 and parts[1] else "medium")
        if priority not in ("high", "medium", "low"):
            priority = "medium"

        deadline_raw = parts[2] if len(parts) > 2 else ""
        deadline = ""
        if deadline_raw:
            parsed = parse_deadline_input(deadline_raw)
            if parsed:
                deadline = parsed
            else:
                errors.append(f"خط {i}: تاریخ نامعتبر «{deadline_raw}» — بدون مهلت ثبت شد")

        category = parts[3][:80] if len(parts) > 3 else ""
        tags = parts[4][:120] if len(parts) > 4 else ""
        description = parts[5][:500] if len(parts) > 5 else ""

        try:
            tid = create_task(
                user_id=update.effective_user.id,
                title=title,
                priority=priority,
                deadline=deadline,
                category=category,
                tags=tags,
                description=description,
            )
            created.append((tid, title))
        except Exception as e:
            errors.append(f"خط {i}: خطا در ثبت — {e}")

    context.user_data.pop("step", None)

    if not created and not errors:
        await update.message.reply_text("هیچ تسکی ثبت نشد.")
        return True

    lines_out = [f"✅ **{len(created)}** تسک ثبت شد.\n"]
    for tid, title in created[:15]:
        lines_out.append(f"• `{tid}` — {title}")
    if len(created) > 15:
        lines_out.append(f"... و {len(created) - 15} مورد دیگر")

    if errors:
        lines_out.append(f"\n⚠️ هشدار/خطا ({len(errors)}):")
        for e in errors[:8]:
            lines_out.append(f"• {e}")

    await update.message.reply_text("\n".join(lines_out), parse_mode="Markdown")
    return True
