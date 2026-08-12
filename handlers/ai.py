"""AI assistant and natural-language task/habit creation."""

import asyncio

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.groq_service import (
    GroqConfigurationError,
    GroqRequestError,
    ask_task_assistant,
    parse_task_request,
)
from services.habit_service import create_habit, get_habit
from services.task_service import create_task_async


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
        "🤖 دستیار هوشمند\n\n"
        "می‌توانید سؤال بپرسید یا تسک و عادت را به زبان طبیعی بنویسید.\n\n"
        "💡 مثال‌های کاربردی:\n\n"
        "📝 ساخت تسک\n«گزارش فروش ماهانه را آماده کنم»\n\n"
        "⏰ تعیین ساعت\n«امروز ساعت ۲ جلسه با شرکت مدیران خودرو دارم»\n\n"
        "📅 تعیین موعد\n«فردا گزارش پروژه را برای مدیرم ارسال کنم»\n\n"
        "🔴 تعیین اولویت\n«پرداخت فاکتور شرکت را برای امروز با اولویت بالا ثبت کن»\n\n"
        "🏷 افزودن تگ\n«فردا قرارداد جدید را بررسی کنم با تگ قرارداد»\n\n"
        "🌱 ساخت عادت\n«هر روز ساعت ۸ صبح ورزش کنم»\n\n"
        "⏰ عادت چندباره\n«هر روز ساعت ۸ و ۱۴ آب بخورم»\n\n"
        "🔁 عادت هفتگی\n«هر هفته سه بار ورزش کنم»\n\n"
        "💬 پرسیدن سؤال\n«امروز مهم‌ترین کارهایی که باید انجام بدهم چیست؟»\n\n"
        "👇 برای کپی هر مثال، روی دکمه آن بزنید."
    )


def _ai_examples_keyboard() -> InlineKeyboardMarkup:
    examples = _AI_EXAMPLES + [
        ("🌱 ساخت عادت", "/ai هر روز ساعت ۸ صبح ورزش کنم"),
        ("⏰ عادت چندباره", "/ai هر روز ساعت ۸ و ۱۴ آب بخورم"),
        ("🔁 عادت هفتگی", "/ai هر هفته سه بار ورزش کنم"),
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 {label}", copy_text=CopyTextButton(text=example))]
        for label, example in examples
    ])


def _draft_text(draft: dict) -> str:
    if draft.get("action") == "CREATE_HABIT":
        lines = ["🤖 عادت پیشنهادی هوش مصنوعی", "", f"🌱 عنوان: {draft['title']}"]
        lines.append(f"🔁 تکرار: {_REPEAT_LABEL.get(draft.get('repeat_type'), 'روزانه')}")
        if draft.get("target"):
            lines.append(f"🎯 هدف: {draft['target']}")
        if draft.get("reminder_time"):
            lines.append(f"⏰ یادآوری: {draft['reminder_time'].replace(',', '، ')}")
        else:
            lines.append("⏰ یادآوری: بدون زمان مشخص")
        if draft.get("category"):
            lines.append(f"📂 دسته‌بندی: {draft['category']}")
        if draft.get("tags"):
            lines.append(f"🏷 تگ: {draft['tags']}")
        if draft.get("description"):
            lines.append(f"📝 توضیح: {draft['description']}")
        lines.extend(["", "این مورد به بخش عادت‌ها اضافه شود؟"])
        return "\n".join(lines)

    lines = ["🤖 تسک پیشنهادی هوش مصنوعی", "", f"📌 عنوان: {draft['title']}"]
    if draft.get("deadline"):
        lines.append(f"🗓 موعد: {draft['deadline']}")
    lines.append(f"🎯 اولویت: {_PRIORITY_LABEL.get(draft.get('priority'), '🟠 متوسط')}")
    if draft.get("category"):
        lines.append(f"📂 دسته‌بندی: {draft['category']}")
    if draft.get("tags"):
        lines.append(f"🏷 تگ: {draft['tags']}")
    if draft.get("description"):
        lines.append(f"📝 توضیح: {draft['description']}")
    lines.extend(["", "آیا این تسک ایجاد شود?"])
    return "\n".join(lines)


def _draft_keyboard(action: str) -> InlineKeyboardMarkup:
    prefix = "ai_habit" if action == "CREATE_HABIT" else "ai_task"
    label = "🌱 افزودن به عادت‌ها" if action == "CREATE_HABIT" else "✅ ایجاد تسک"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{prefix}_create")],
        [InlineKeyboardButton("❌ لغو", callback_data=f"{prefix}_cancel")],
    ])


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request_text = " ".join(context.args).strip()
    if not request_text:
        await update.message.reply_text(_ai_examples_text(), reply_markup=_ai_examples_keyboard())
        return

    try:
        draft = await asyncio.to_thread(parse_task_request, update.effective_user.id, request_text)
        if draft.get("action") in {"CREATE_TASK", "CREATE_HABIT"}:
            context.user_data["ai_request_draft"] = draft
            await update.message.reply_text(_draft_text(draft), reply_markup=_draft_keyboard(draft["action"]))
            return
        answer = await asyncio.to_thread(ask_task_assistant, update.effective_user.id, request_text)
    except GroqConfigurationError:
        await update.message.reply_text("⚠️ دستیار هوشمند در حال حاضر فعال نیست.")
        return
    except GroqRequestError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    # پاسخ بدون داده مرتبط نباید برای کاربر ارسال شود.
    if not answer:
        return
    await update.message.reply_text(f"🤖 {answer}")


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
    context.user_data.pop("ai_request_draft", None)
    try:
        task_id = await create_task_async(
            update.effective_user.id,
            draft["title"],
            draft.get("priority", "medium"),
            draft.get("deadline", ""),
            draft.get("category", ""),
            draft.get("tags", ""),
            draft.get("description", ""),
        )
    except Exception:
        context.user_data["ai_request_draft"] = draft
        await query.edit_message_text("⚠️ ایجاد تسک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        return
    await query.edit_message_text(
        f"✅ تسک با موفقیت ایجاد شد.\n\n📌 {draft['title']}\n🆔 {task_id}"
        + (f"\n🗓 {draft['deadline']}" if draft.get("deadline") else "")
    )


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
    context.user_data.pop("ai_request_draft", None)
    try:
        habit_id = await asyncio.to_thread(
            create_habit,
            update.effective_user.id,
            draft["title"],
            draft.get("category", ""),
            draft.get("description", ""),
            draft.get("repeat_type", "daily"),
            draft.get("target", ""),
            draft.get("reminder_time", ""),
            "",
        )
        habit = await asyncio.to_thread(get_habit, habit_id)
    except Exception:
        context.user_data["ai_request_draft"] = draft
        await query.edit_message_text("⚠️ ایجاد عادت با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        return

    repeat = _REPEAT_LABEL.get(draft.get("repeat_type"), "روزانه")
    reminder = draft.get("reminder_time") or "بدون یادآوری"
    await query.edit_message_text(
        "✅ عادت با موفقیت به بخش عادت‌ها اضافه شد.\n\n"
        f"🌱 {habit.get('title', draft['title'])}\n"
        f"🔁 تکرار: {repeat}\n"
        f"⏰ یادآوری: {reminder}\n"
        f"🆔 {habit_id}"
    )
