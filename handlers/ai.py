"""AI assistant and natural-language task/habit creation."""

import asyncio
from datetime import datetime

import jdatetime
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.admin_service import notify_ai_parse_failure
from services.groq_service import GroqConfigurationError, GroqRequestError, ask_task_assistant, get_processing_status_messages
from services.task_intelligence import parse_task_request_smart
from services.habit_service import create_habit, get_habit
from services.task_service import create_task_async, get_task_by_id_async, get_task_comments_async
from utils.keyboard import task_action_keyboard
from handlers.task import format_task_card

_PRIORITY_LABEL = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}
_REPEAT_LABEL = {"daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه"}

_AI_EXAMPLES = [
    ("📝 ساخت تسک", "/ai گزارش فروش ماهانه را آماده کنم"),
    ("⏰ تعیین ساعت", "/ai امروز ساعت ۲ جلسه با شرکت مدیران خودرو دارم"),
    ("📅 تعیین موعد", "/ai فردا گزارش پروژه را برای مدیرم ارسال کنم"),
    ("🔴 تعیین اولویت", "/ai پرداخت فاکتور شرکت را برای امروز با اولویت بالا ثبت کن"),
    ("🏷 افزودن تگ", "/ai فردا قرارداد جدید را بررسی کنم با تگ قرارداد"),
    ("💬 پرسیدن سؤال", "/ai امروز مهم‌ترین کارهایی که باید انجام بدهم چیست؟"),
]

def _ai_examples_text() -> str:
    return (
        "🤖 دستیار هوشمند\n\nمی‌توانید سؤال بپرسید یا تسک و عادت را به زبان طبیعی بنویسید.\n\n"
        "💡 مثال‌های کاربردی:\n\n📝 ساخت تسک\n«گزارش فروش ماهانه را آماده کنم»\n\n"
        "⏰ تعیین ساعت\n«امروز ساعت ۲ جلسه با شرکت مدیران خودرو دارم»\n\n"
        "📅 تعیین موعد\n«فردا گزارش پروژه را برای مدیرم ارسال کنم»\n\n"
        "🔴 تعیین اولویت\n«پرداخت فاکتور شرکت را برای امروز با اولویت بالا ثبت کن»\n\n"
        "🏷 افزودن تگ\n«فردا قرارداد جدید را بررسی کنم با تگ قرارداد»\n\n"
        "🌱 ساخت عادت\n«هر روز ساعت ۸ صبح ورزش کنم»\n\n"
        "⏰ عادت چندباره\n«هر روز ساعت ۸ و ۱۴ آب بخورم»\n\n"
        "🔁 عادت هفتگی\n«هر هفته سه بار ورزش کنم»\n\n"
        "💬 پرسیدن سؤال\n«امروز مهم‌ترین کارهایی که باید انجام بدهم چیست؟»\n\n👇 برای کپی هر مثال، روی دکمه آن بزنید."
    )

def _ai_examples_keyboard() -> InlineKeyboardMarkup:
    examples = _AI_EXAMPLES + [("🌱 ساخت عادت", "/ai هر روز ساعت ۸ صبح ورزش کنم"), ("⏰ عادت چندباره", "/ai هر روز ساعت ۸ و ۱۴ آب بخورم"), ("🔁 عادت هفتگی", "/ai هر هفته سه بار ورزش کنم")]
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"📋 {label}", copy_text=CopyTextButton(text=example))] for label, example in examples])

def _format_deadline_both_calendars(value: str) -> tuple[str, str, str]:
    text = str(value or "").strip()
    if not text:
        return "—", "—", "—"
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text[:19], fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return text, "—", "—"
    gregorian = parsed.strftime("%Y/%m/%d")
    jalali = jdatetime.date.fromgregorian(date=parsed.date()).strftime("%Y/%m/%d")
    time_value = parsed.strftime("%H:%M") if len(text) > 10 and text[10:11] in {" ", "T"} else "—"
    return gregorian, jalali, time_value

def _draft_text(draft: dict) -> str:
    missing = "—"
    if draft.get("action") == "CREATE_HABIT":
        return "\n".join(["🤖 عادت پیشنهادی هوش مصنوعی", "", f"🌱 عنوان: {draft.get('title') or missing}", f"🔁 تکرار: {_REPEAT_LABEL.get(draft.get('repeat_type'), missing)}", f"🎯 هدف: {draft.get('target') or missing}", f"⏰ یادآوری: {draft.get('reminder_time') or missing}", f"📂 دسته‌بندی: {draft.get('category') or missing}", f"🏷 تگ: {draft.get('tags') or missing}", f"📝 توضیح: {draft.get('description') or missing}", "", "این مورد به بخش عادت‌ها اضافه شود?"])
    gregorian, jalali, time_value = _format_deadline_both_calendars(draft.get("deadline", ""))
    return "\n".join(["🤖 تسک پیشنهادی هوش مصنوعی", "", f"📌 عنوان: {draft.get('title') or missing}", f"🗓 موعد میلادی: {gregorian}", f"📅 موعد شمسی: {jalali}", f"⏰ ساعت: {time_value}", f"🎯 اولویت: {_PRIORITY_LABEL.get(draft.get('priority'), '🟢 پایین')}", f"📂 دسته‌بندی: {draft.get('category') or missing}", f"🏷 تگ: {draft.get('tags') or missing}", f"📝 توضیح: {draft.get('description') or missing}", "", "آیا این تسک ایجاد شود?"])

def _draft_keyboard(action: str) -> InlineKeyboardMarkup:
    prefix = "ai_habit" if action == "CREATE_HABIT" else "ai_task"
    label = "🌱 افزودن به عادت‌ها" if action == "CREATE_HABIT" else "✅ ایجاد تسک"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f"{prefix}_create")], [InlineKeyboardButton("❌ لغو", callback_data=f"{prefix}_cancel")]])

def _task_card_for_ai(task: dict) -> str:
    normalized = dict(task)
    raw_deadline = str(normalized.get("deadline") or "").strip()
    time_value = "—"
    if len(raw_deadline) >= 16 and raw_deadline[10:11] in {" ", "T"}:
        time_value = raw_deadline[11:16]
        normalized["deadline"] = raw_deadline[:10]
    text = format_task_card(normalized)
    text = text.replace("📅 مهلت: بدون ددلاین", "📅 مهلت: —")
    return text + f"\n⏰ ساعت: {time_value}"

async def _run_with_processing(message, operation):
    statuses = get_processing_status_messages()
    status_message = await message.reply_text(statuses[0])
    task = asyncio.create_task(asyncio.to_thread(operation))
    index = 1
    try:
        while not task.done():
            await asyncio.sleep(0.35)
            if task.done():
                break
            await status_message.edit_text(statuses[index % len(statuses)])
            index += 1
        result = await task
        await status_message.delete()
        return result
    except Exception:
        try:
            await status_message.delete()
        except Exception:
            pass
        raise

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request_text = " ".join(context.args).strip()
    if not request_text:
        await update.message.reply_text(_ai_examples_text(), reply_markup=_ai_examples_keyboard())
        return
    try:
        draft = await _run_with_processing(update.message, lambda: parse_task_request_smart(update.effective_user.id, request_text))
        if draft.get("action") in {"CREATE_TASK", "CREATE_HABIT"}:
            context.user_data["ai_request_draft"] = draft
            await update.message.reply_text(_draft_text(draft), reply_markup=_draft_keyboard(draft["action"]))
            return
        answer = await _run_with_processing(update.message, lambda: ask_task_assistant(update.effective_user.id, request_text))
    except GroqConfigurationError:
        await update.message.reply_text("⚠️ دستیار هوشمند در حال حاضر فعال نیست.")
        return
    except GroqRequestError as exc:
        if str(exc) in {"پاسخ ساختاریافته هوش مصنوعی قابل پردازش نبود.", "پاسخ ساختاریافته هوش مصنوعی نامعتبر است."}:
            await notify_ai_parse_failure(update, context, request_text, exc)
        await update.message.reply_text(f"⚠️ {exc}")
        return
    if answer:
        await update.message.reply_text(f"🤖 {answer}", parse_mode=ParseMode.HTML)

async def ai_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    draft = context.user_data.get("ai_request_draft")
    if query.data == "ai_task_cancel":
        context.user_data.pop("ai_request_draft", None)
        await query.edit_message_text("❌ ایجاد تسک لغو شد.")
        return
    if not draft or draft.get("action") != "CREATE_TASK":
        await query.edit_message_text("⚠️ پیش‌نویس تسک منقضی شده است. دوباره درخواست را ارسال کنید.")
        return
    try:
        task_id = await create_task_async(update.effective_user.id, draft.get("title", ""), draft.get("priority", "medium"), draft.get("deadline", ""), draft.get("category", ""), draft.get("tags", ""), draft.get("description", ""))
        task = await get_task_by_id_async(task_id)
        comments_count = len(await get_task_comments_async(task_id))
    except Exception:
        context.user_data["ai_request_draft"] = draft
        await query.edit_message_text("⚠️ ایجاد تسک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        return
    context.user_data.pop("ai_request_draft", None)
    if not task:
        await query.edit_message_text(f"✅ تسک ایجاد شد.\n\n🆔 شناسه: {task_id}")
        return
    keyboard = task_action_keyboard(task.get("id", task_id), task.get("status", "pending"), context.bot_data.get("bot_config"), comment_count=comments_count)
    await query.edit_message_text("🤖 تسک با موفقیت ایجاد شد.\n\n" + _task_card_for_ai(task), reply_markup=keyboard, parse_mode="Markdown")

async def ai_habit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    draft = context.user_data.get("ai_request_draft")
    if query.data == "ai_habit_cancel":
        context.user_data.pop("ai_request_draft", None)
        await query.edit_message_text("❌ ایجاد عادت لغو شد.")
        return
    if not draft or draft.get("action") != "CREATE_HABIT":
        await query.edit_message_text("⚠️ پیش‌نویس عادت منقضی شده است. دوباره درخواست را ارسال کنید.")
        return
    try:
        habit_id = await asyncio.to_thread(create_habit, update.effective_user.id, draft["title"], draft.get("category", ""), draft.get("description", ""), draft.get("repeat_type", "daily"), draft.get("target", ""), draft.get("reminder_time", ""), "")
        habit = await asyncio.to_thread(get_habit, habit_id)
    except Exception:
        context.user_data["ai_request_draft"] = draft
        await query.edit_message_text("⚠️ ایجاد عادت با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        return
    context.user_data.pop("ai_request_draft", None)
    repeat = _REPEAT_LABEL.get(draft.get("repeat_type"), "روزانه")
    reminder = draft.get("reminder_time") or "بدون یادآوری"
    await query.edit_message_text("✅ عادت با موفقیت به بخش عادت‌ها اضافه شد.\n\n" + f"🌱 {habit.get('title', draft['title'])}\n" + f"🔁 تکرار: {repeat}\n" + f"⏰ یادآوری: {reminder}\n" + f"🆔 {habit_id}")
