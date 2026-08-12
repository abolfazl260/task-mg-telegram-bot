"""AI assistant and natural-language task creation."""

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.groq_service import (
    GroqConfigurationError,
    GroqRequestError,
    ask_task_assistant,
    parse_task_request,
)
from services.task_service import create_task_async


_PRIORITY_LABEL = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}


def _draft_text(draft: dict) -> str:
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
    lines.extend(["", "آیا این تسک ایجاد شود؟"])
    return "\n".join(lines)


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request_text = " ".join(context.args).strip()
    if not request_text:
        await update.message.reply_text(
            "🤖 دستیار هوشمند\n\n"
            "می‌توانید سؤال بپرسید یا تسک را به زبان طبیعی بنویسید.\n\n"
            "مثال:\n"
            "/ai برای امروز جلسه ساعت ۲ دارم با شرکت مدیران خودرو"
        )
        return

    waiting = await update.message.reply_text("🤖 در حال تحلیل درخواست شما...")
    try:
        draft = await asyncio.to_thread(parse_task_request, update.effective_user.id, request_text)
        if draft.get("action") == "CREATE_TASK":
            context.user_data["ai_task_draft"] = draft
            await waiting.edit_text(
                _draft_text(draft),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ایجاد تسک", callback_data="ai_task_create")],
                    [InlineKeyboardButton("❌ لغو", callback_data="ai_task_cancel")],
                ]),
            )
            return
        answer = await asyncio.to_thread(ask_task_assistant, update.effective_user.id, request_text)
    except GroqConfigurationError:
        await waiting.edit_text("⚠️ برای فعال شدن دستیار هوشمند، متغیر GROQ_API_KEY را در .env تنظیم کنید.")
        return
    except GroqRequestError as exc:
        await waiting.edit_text(f"⚠️ {exc}")
        return

    await waiting.edit_text(f"🤖 پاسخ دستیار:\n\n{answer}")


async def ai_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.pop("ai_task_draft", None)
    if query.data == "ai_task_cancel":
        await query.edit_message_text("❌ ایجاد تسک لغو شد.")
        return
    if not draft:
        await query.edit_message_text("⚠️ پیش‌نویس تسک منقضی شده است. دوباره درخواست را ارسال کنید.")
        return
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
        context.user_data["ai_task_draft"] = draft
        await query.edit_message_text("⚠️ ایجاد تسک با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        return
    await query.edit_message_text(
        f"✅ تسک با موفقیت ایجاد شد.\n\n📌 {draft['title']}\n🆔 {task_id}"
        + (f"\n🗓 {draft['deadline']}" if draft.get("deadline") else "")
    )
