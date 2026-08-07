"""Bulk import tasks from structured text or CSV files."""

import csv
import io
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.task_service import create_task
from utils.date_parse import parse_deadline_input

CSV_COLUMNS = ["title", "priority", "deadline", "category", "tags", "description"]
CSV_SAMPLE_PATH = Path(__file__).resolve().parent.parent / "samples" / "task_import_sample.csv"
MAX_CSV_ROWS = 100

IMPORT_HELP = """📥 ایمپورت گروهی

دو روش برای ثبت چند کار به‌صورت یک‌جا دارید:

1) 📝 ورود متنی
همان روش فعلی با فرمت TASKS و جداکننده |.

2) 📄 آپلود CSV
ابتدا «دانلود فایل نمونه CSV» را بزنید، فایل را با Excel / Google Sheets / Numbers ویرایش کنید، با فرمت CSV ذخیره کنید و دوباره برای ربات بفرستید.

فرمت متنی هر خط:
عنوان | اولویت | مهلت | دسته | تگ | توضیح

مثال قابل کپی:
```
TASKS
خرید نان | medium |  | خرید |  | ۲ عدد
```

ستون‌های CSV:
title,priority,deadline,category,tags,description

قوانین: title الزامی است؛ priority فقط high / medium / low؛ deadline باید تاریخ معتبر یا خالی باشد.
"""

GPT_PROMPT = """این متن را به ChatGPT بده:

---
لیست زیر را فقط به این فرمت تبدیل کن (بدون توضیح اضافه):

TASKS
عنوان | اولویت | مهلت | دسته | تگ | توضیح

قواعد:
- اولویت فقط: high یا medium یا low
- مهلت: YYYY-MM-DD یا خالی
- هر خط یک کار
- فیلد خالی را خالی بگذار
- حداکثر ۳۰ خط

لیست من:
[اینجا بنویس]
---
"""
SAMPLE_TEMPLATES = {
    "checklist": {
        "title": "چک‌لیست",
        "body": """TASKS
بررسی مدارک هویتی | high |  | چک‌لیست | مهم | کارت ملی و شناسنامه
پر کردن فرم ثبت‌نام | high |  | چک‌لیست |  | 
پرداخت هزینه | medium |  | چک‌لیست | مالی | فیش را نگه دار
ارسال مدارک در واتساپ | medium |  | چک‌لیست |  | به شماره پشتیبانی
تأیید نهایی از مسئول | high |  | چک‌لیست | مهم | 
بایگانی کپی مدارک | low |  | چک‌لیست |  | """,
    },
    "shopping": {
        "title": "لیست خرید",
        "body": """TASKS
نان سنگک | medium |  | خرید | نانوایی | ۲ عدد
شیر کم‌چرب ۱ لیتری | medium |  | خرید | لبنیات | 
تخم‌مرغ شانه ۳۰ تایی | medium |  | خرید | پروتئین | 
برنج طارم ۲ کیلو | low |  | خرید | خشکبار | 
گوجه‌فرنگی ۱ کیلو | medium |  | خرید | سبزیجات | 
خیار | low |  | خرید | سبزیجات | 
ماست سطل کوچک | medium |  | خرید | لبنیات | 
مایع ظرفشویی | low |  | خرید | منزل | 
دستمال کاغذی | low |  | خرید | منزل | """,
    },
    "study": {
        "title": "برنامه درسی",
        "body": """TASKS
زیست — مولکول‌های اطلاعاتی ص ۱ تا ۱۶ | high |  | مطالعه | زیست | خلاصه + فلش‌کارت
فیزیک — حرکت بر خط راست ص ۱ تا ۲۶ | high |  | مطالعه | فیزیک | مثال‌های کتاب
شیمی — قدردانی از زحمات ص ۱ تا ۲۴ | medium |  | مطالعه | شیمی | 
ریاضی — تابع ص ۱ تا ۴۶ | high |  | مطالعه | ریاضی | تمرین‌های زوج
تست زیست — ۲۰ سؤال | medium |  | مطالعه | تست | غلط‌ها را بنویس
مرور فیزیک هفته | medium |  | مطالعه | مرور | فقط فرمول‌ها
فارسی — درس ۱ | low |  | مطالعه | عمومی | """,
    },
    "shift": {
        "title": "شیفت رستوران",
        "body": """TASKS
شیفت صبح ۸–۱۴ — علی محمدی — باز کردن سالن | high |  | شیفت رستوران | صبح علی | کلید، برق، چیدمان میز
شیفت صبح ۸–۱۴ — علی محمدی — کنترل یخچال و انبار | high |  | شیفت رستوران | صبح علی | کسری را در دفتر بنویس
شیفت صبح ۸–۱۴ — سارا احمدی — صندوق و پذیرش | high |  | شیفت رستوران | صبح سارا | 
شیفت ظهر ۱۴–۲۰ — رضا کریمی — سالن و سفارش‌ها | medium |  | شیفت رستوران | ظهر رضا | 
شیفت ظهر ۱۴–۲۰ — مریم حسینی — کمک آشپزخانه | medium |  | شیفت رستوران | ظهر مریم | 
شیفت عصر ۲۰–۲۴ — حسین نوری — سالن | medium |  | شیفت رستوران | عصر حسین | 
شیفت شب ۲۰–۲۴ — نگین رضایی — بستن صندوق | high |  | شیفت رستوران | شب نگین | شمارش وجه و گزارش
شیفت شب ۲۰–۲۴ — نگین رضایی — نظافت نهایی | high |  | شیفت رستوران | شب نگین | سالن و آشپزخانه
تحویل شیفت — علی به رضا | medium |  | شیفت رستوران | تحویل | موارد باز را شفاهی و کتبی بگو
تحویل شیفت — رضا به نگین | medium |  | شیفت رستوران | تحویل | """,
    },
}


def _samples_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ چک‌لیست", callback_data="import_tpl_checklist")],
        [InlineKeyboardButton("🛒 لیست خرید", callback_data="import_tpl_shopping")],
        [InlineKeyboardButton("📚 برنامه درسی", callback_data="import_tpl_study")],
        [InlineKeyboardButton("🍽️ شیفت رستوران", callback_data="import_tpl_shift")],
        [InlineKeyboardButton("📄 دانلود فایل نمونه CSV", callback_data="import_download_csv_sample")],
        [InlineKeyboardButton("🤖 پرامپت ChatGPT", callback_data="import_show_prompt")],
        [InlineKeyboardButton("❌ انصراف", callback_data="import_cancel")],
    ])


async def start_import_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["step"] = "import_bulk"

    if update.callback_query:
        msg = update.callback_query.message
    else:
        msg = update.message

    await msg.reply_text(IMPORT_HELP, reply_markup=_samples_keyboard(), parse_mode="Markdown")


async def import_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "import_bulk":
        await start_import_flow(update, context)
        return

    if data == "import_download_csv_sample":
        context.user_data["step"] = "import_bulk"
        with CSV_SAMPLE_PATH.open("rb") as sample_file:
            await query.message.reply_document(
                document=sample_file,
                filename="task_import_sample.csv",
                caption=(
                    "📄 فایل نمونه CSV آماده است.\n"
                    "آن را ویرایش کنید، با فرمت CSV ذخیره کنید و دوباره برای ربات ارسال کنید."
                ),
            )
        return

    if data == "import_show_prompt":
        context.user_data["step"] = "import_bulk"
        await query.message.reply_text(
            "🤖 پرامپت ChatGPT\n\n" + GPT_PROMPT
        )
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
            f"۱) متن زیر را کپی کن\n"
            f"۲) اسم‌ها یا موارد را عوض کن اگر لازم است\n"
            f"۳) همین متن را دوباره اینجا بفرست"
        )
        await query.message.reply_text(f"```\n{sample['body']}\n```", parse_mode="Markdown")
        return


    if data == "import_csv_confirm":
        rows = context.user_data.pop("import_csv_valid_rows", [])
        error_count = context.user_data.pop("import_csv_error_count", 0)
        context.user_data.pop("step", None)
        if not rows:
            await query.message.reply_text("⚠️ داده معتبری برای ثبت پیدا نشد. لطفاً فایل CSV را دوباره ارسال کنید.")
            return
        created = []
        for row in rows:
            tid = create_task(user_id=update.effective_user.id, **row)
            created.append((tid, row["title"], row["priority"]))
        lines = ["✅ ایمپورت با موفقیت انجام شد", "", f"{len(created)} تسک ایجاد شد.", ""]
        for _, title, priority in created[:3]:
            lines.append(f"• {title} — {priority.upper()}")
        if len(created) > 3:
            lines.append(f"... و {len(created) - 3} مورد دیگر")
        if error_count:
            lines.append("")
            lines.append(f"{error_count} ردیف به دلیل خطا ثبت نشدند.")
        await query.message.reply_text("\n".join(lines))
        return

    if data == "import_csv_cancel":
        context.user_data.pop("import_csv_valid_rows", None)
        context.user_data.pop("import_csv_error_count", None)
        context.user_data.pop("step", None)
        await query.message.reply_text("ایمپورت CSV لغو شد و هیچ تسکی ثبت نشد.")
        return

    if data == "import_cancel":
        context.user_data.pop("step", None)
        await query.message.reply_text("ایمپورت لغو شد.")
        return


def _looks_like_task_line(line: str) -> bool:
    """A valid task line should have | separators or be clearly structured."""
    if "|" in line:
        return True
    return False



def _csv_error(row_number: int, column: str, reason: str) -> str:
    return f"خط {row_number} → {column}: {reason}"


def _validate_csv_rows(csv_bytes: bytes):
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [col for col in CSV_COLUMNS if col not in headers]
    if missing:
        return [], [_csv_error(1, ", ".join(missing), "ستون اجباری در هدر فایل وجود ندارد")], 0

    valid_rows = []
    errors = []
    total_rows = 0
    for row_number, raw in enumerate(reader, start=2):
        row = {(key or "").strip(): value for key, value in raw.items() if key is not None}
        if not any(str(value or "").strip() for value in row.values()):
            continue
        total_rows += 1
        row_errors = []
        title = (row.get("title") or "").strip()
        if not title:
            row_errors.append(_csv_error(row_number, "title", "عنوان تسک الزامی است"))

        priority_raw = (row.get("priority") or "").strip().lower()
        priority = priority_raw or "medium"
        if priority not in ("high", "medium", "low"):
            row_errors.append(_csv_error(row_number, "priority", f"مقدار «{priority_raw}» معتبر نیست"))

        deadline_raw = (row.get("deadline") or "").strip()
        deadline = ""
        if deadline_raw:
            parsed = parse_deadline_input(deadline_raw)
            if parsed:
                deadline = parsed
            else:
                row_errors.append(_csv_error(row_number, "deadline", "تاریخ نامعتبر است"))

        if row_errors:
            errors.extend(row_errors)
            continue

        valid_rows.append({
            "title": title[:200],
            "priority": priority,
            "deadline": deadline,
            "category": (row.get("category") or "").strip()[:80],
            "tags": (row.get("tags") or "").strip()[:120],
            "description": (row.get("description") or "").strip()[:500],
        })
    return valid_rows, errors, total_rows


def _csv_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ ثبت تسک‌ها", callback_data="import_csv_confirm"),
        InlineKeyboardButton("❌ لغو", callback_data="import_csv_cancel"),
    ]])


async def handle_import_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("step") != "import_bulk" or not update.message or not update.message.document:
        return False

    document = update.message.document
    filename = document.file_name or ""
    if not filename.lower().endswith(".csv"):
        await update.message.reply_text("⚠️ لطفاً فایل را با فرمت CSV ارسال کنید.")
        return True
    if document.file_size and document.file_size > 1024 * 1024:
        await update.message.reply_text("⚠️ فایل خیلی بزرگ است. حداکثر اندازه قابل قبول ۱ مگابایت است.")
        return True

    tg_file = await document.get_file()
    data = await tg_file.download_as_bytearray()
    valid_rows, errors, total_rows = _validate_csv_rows(bytes(data))
    if total_rows > MAX_CSV_ROWS:
        await update.message.reply_text(f"⚠️ فایل بیش از حد بزرگ است. حداکثر {MAX_CSV_ROWS} ردیف داده مجاز است.")
        return True

    context.user_data["import_csv_valid_rows"] = valid_rows
    context.user_data["import_csv_error_count"] = len(errors)
    lines = [
        "📥 نتیجه بررسی فایل",
        "",
        f"تعداد ردیف‌ها: {total_rows}",
        f"✅ آماده ثبت: {len(valid_rows)}",
        f"❌ دارای خطا: {len(errors)}",
    ]
    if errors:
        lines.append("")
        lines.extend(errors[:10])
        if len(errors) > 10:
            lines.append(f"... و {len(errors) - 10} خطای دیگر")
    if valid_rows:
        lines.append("")
        lines.append(f"آیا {len(valid_rows)} تسک صحیح ثبت شوند؟")
        await update.message.reply_text("\n".join(lines), reply_markup=_csv_preview_keyboard())
    else:
        lines.append("")
        lines.append("هیچ ردیف سالمی برای ثبت وجود ندارد. فایل را اصلاح و دوباره ارسال کنید.")
        await update.message.reply_text("\n".join(lines))
    return True


async def handle_import_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("step") != "import_bulk":
        return False

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("متن خالی بود. یک نمونه را بزن یا متن با فرمت TASKS بفرست.")
        return True

    if text.lower() in ("cancel", "لغو", "انصراف"):
        context.user_data.pop("step", None)
        await update.message.reply_text("ایمپورت لغو شد.")
        return True

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        await update.message.reply_text("متنی پیدا نشد.")
        return True

    # Strip accidental code fences
    lines = [ln for ln in lines if not ln.startswith("```")]

    has_header = lines[0].upper().startswith("TASKS")
    data_lines = lines[1:] if has_header else lines

    # If no TASKS header and no pipe-separated lines → clear warning
    pipe_lines = [ln for ln in data_lines if "|" in ln]
    if not has_header and not pipe_lines:
        await update.message.reply_text(
            "⚠️ این متن برای ایمپورت گروهی مناسب نیست.\n\n"
            "باید به این شکل باشد:\n\n"
            "TASKS\n"
            "عنوان | medium |  | دسته | تگ | توضیح\n\n"
            "یا یکی از دکمه‌های نمونه (چک‌لیست، خرید، درسی، شیفت) را بزن "
            "و همان متن را بعد از ویرایش بفرست.\n\n"
            "برای لغو بنویس: لغو",
            reply_markup=_samples_keyboard(),
        )
        return True

    if not data_lines:
        await update.message.reply_text(
            "⚠️ بعد از کلمه TASKS هیچ کاری نوشته نشده.\n"
            "حداقل یک خط مثل این لازم است:\n"
            "خرید نان | medium |  | خرید |  | ",
            reply_markup=_samples_keyboard(),
        )
        return True

    if len(text) > 4000:
        await update.message.reply_text(
            "⚠️ متن خیلی طولانی است.\n"
            "حداکثر حدود ۳۰ کار در هر پیام بفرست."
        )
        return True

    # If header missing but pipes exist, accept with a soft note
    soft_note = ""
    if not has_header and pipe_lines:
        soft_note = "ℹ️ خط TASKS نبود؛ از خطوط دارای | خواندم.\n"

    created = []
    errors = []
    skipped = 0

    for i, line in enumerate(data_lines, start=1):
        if "|" not in line:
            skipped += 1
            errors.append(f"خط {i}: فرمت درست نیست (علامت | ندارد) — رد شد")
            continue

        parts = [p.strip() for p in line.split("|")]
        if not parts[0]:
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
                errors.append(f"خط {i}: تاریخ «{deadline_raw}» نامعتبر — بدون مهلت ثبت شد")

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
            errors.append(f"خط {i}: ثبت نشد — {e}")

    if not created:
        await update.message.reply_text(
            "⚠️ هیچ کاری ثبت نشد.\n\n"
            "متن را با این شکل بفرست:\n"
            "TASKS\n"
            "عنوان | medium |  | دسته | تگ | توضیح\n\n"
            "یا از نمونه‌های آماده استفاده کن.",
            reply_markup=_samples_keyboard(),
        )
        return True

    context.user_data.pop("step", None)

    lines_out = []
    if soft_note:
        lines_out.append(soft_note)
    lines_out.append(f"✅ {len(created)} کار ثبت شد.\n")
    for tid, title in created[:15]:
        lines_out.append(f"• {tid} — {title}")
    if len(created) > 15:
        lines_out.append(f"... و {len(created) - 15} مورد دیگر")

    if errors:
        lines_out.append(f"\n⚠️ توجه ({len(errors)}):")
        for e in errors[:8]:
            lines_out.append(f"• {e}")

    await update.message.reply_text("\n".join(lines_out))
    return True
