from __future__ import annotations

import asyncio
import logging

from telegram import InputFile, Update
from telegram.error import BadRequest, TimedOut
from telegram.ext import ContextTypes

from services.calendar_pdf_service import build_calendar_pdf
from services.task_service import get_all_user_tasks_async

logger = logging.getLogger(__name__)


async def calendar_pdf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TimedOut):
        pass

    user_id = update.effective_user.id
    try:
        tasks = await get_all_user_tasks_async(user_id)
        pdf = await asyncio.to_thread(build_calendar_pdf, tasks, user_id)
        await query.message.reply_document(
            document=InputFile(pdf, filename="jalali-monthly-calendar.pdf"),
            caption="📅 تقویم ماهانه شمسی آماده است.",
            read_timeout=60,
            write_timeout=60,
            connect_timeout=60,
            pool_timeout=60,
        )
    except TimedOut:
        logger.exception("Timed out sending Jalali calendar PDF user=%s", user_id)
        await query.message.reply_text("⚠️ ارسال فایل PDF زمان‌بر شد. لطفاً دوباره تلاش کنید.")
    except Exception:
        logger.exception("Jalali calendar PDF generation failed user=%s", user_id)
        await query.message.reply_text("⚠️ تولید PDF تقویم ماهانه ناموفق بود. لطفاً دوباره تلاش کنید.")
