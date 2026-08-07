"""AI assistant command powered by Groq."""

from telegram import Update
from telegram.ext import ContextTypes

from services.groq_service import GroqConfigurationError, GroqRequestError, ask_task_assistant


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text(
            "🤖 دستیار هوشمند تسک\n\n"
            "سؤال خود را بعد از دستور بنویسید. مثال:\n"
            "`/ai امروز روی چه کاری تمرکز کنم؟`",
            parse_mode="Markdown",
        )
        return

    waiting = await update.message.reply_text("🤖 در حال تحلیل تسک‌ها با Groq...")
    try:
        answer = ask_task_assistant(update.effective_user.id, question)
    except GroqConfigurationError:
        await waiting.edit_text("⚠️ برای فعال شدن دستیار هوشمند، متغیر `GROQ_API_KEY` را در `.env` تنظیم کنید.", parse_mode="Markdown")
        return
    except GroqRequestError as exc:
        await waiting.edit_text(f"⚠️ {exc}")
        return

    await waiting.edit_text(f"🤖 پاسخ دستیار:\n\n{answer}")
