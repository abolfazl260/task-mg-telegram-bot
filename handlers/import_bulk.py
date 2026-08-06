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

ساختار متن را دقیقاً به این شکل بفرستید (می‌توانید کپی کنید):

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
• اولویت: `high` / `medium` / `low` (پیش‌فرض medium)
• مهلت: میلادی یا شمسی یا خالی
• حداکثر حدود ۳۰–۴۰ تسک در هر پیام (محدودیت تلگرام ~۴۰۹۶ کاراکتر)

بعد از ارسال متن، ربات تسک‌ها را ثبت می‌کند.
"""

# Copy-paste prompt for ChatGPT / other AI to generate the block
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


async def start_import_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help + GPT prompt and set step for receiving bulk text."""

    context.user_data["step"] = "import_bulk"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 کپی پرامپت GPT", callback_data="import_show_prompt")],
        [InlineKeyboardButton("❌ انصراف", callback_data="import_cancel")],
    ])

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(IMPORT_HELP, parse_mode="Markdown", reply_markup=keyboard)


async def import_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "import_show_prompt":
        await query.message.reply_text(
            "📋 پرامپت آماده برای ChatGPT (کپی کن):\n\n" + GPT_PROMPT
        )
        return

    if query.data == "import_cancel":
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

    # Allow user to cancel
    if text.lower() in ("cancel", "لغو", "انصراف"):
        context.user_data.pop("step", None)
        await update.message.reply_text("ایمپورت لغو شد.")
        return True

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        await update.message.reply_text("متنی پیدا نشد.")
        return True

    # Expect first non-empty line to be TASKS (case-insensitive)
    start = 0
    if lines[0].upper().startswith("TASKS"):
        start = 1
    else:
        # still try to parse if looks like data rows
        pass

    data_lines = lines[start:]
    if not data_lines:
        await update.message.reply_text(
            "بعد از خط TASKS هیچ تسکی نبود.\n"
            "نمونه:\nTASKS\nعنوان | high | 2026-08-20 | کار | تگ | توضیح"
        )
        return True

    # Telegram soft limit: refuse huge paste
    if len(text) > 4000:
        await update.message.reply_text(
            "⚠️ متن خیلی طولانی است (محدودیت تلگرام).\n"
            "لطفاً حداکثر حدود ۳۰–۴۰ تسک در هر پیام بفرستید و بقیه را جداگانه."
        )
        return True

    created = []
    errors = []

    for i, line in enumerate(data_lines, start=1):
        # skip markdown code fences if user pasted with ```
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
