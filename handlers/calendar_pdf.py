from __future__ import annotations

import asyncio
import logging

from telegram.error import TimedOut

from services.calendar_pdf_service import build_calendar_pdf
from services.task_service import get_all_user_tasks

logger = logging.getLogger(__name__)


async def calendar_pdf_callback(update, context):
    """Generate and send the canonical monthly calendar PDF without blocking updates."""
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    # Acknowledge the callback immediately. PDF generation/upload can take longer
    # than Telegram's callback-query deadline.
    if query:
        try:
            await query.answer("در حال آماده‌سازی PDF تقویم…")
        except Exception:
            logger.debug("Could not answer calendar PDF callback", exc_info=True)

    try:
        # Both DB access and ReportLab rendering are synchronous. Run them off
        # the asyncio event loop so other Telegram updates remain responsive.
        tasks = await asyncio.to_thread(get_all_user_tasks, user.id)
        pdf_buffer = await asyncio.to_thread(build_calendar_pdf, tasks, user.id)
        filename = "تقویم-ماهانه.pdf"
        pdf_buffer.name = filename
        pdf_buffer.seek(0)

        await context.bot.send_chat_action(
            chat_id=chat.id,
            action="upload_document",
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30,
        )

        await context.bot.send_document(
            chat_id=chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="📅 تقویم ماهانه تسک‌ها",
            # PDF upload can be slower than normal Telegram API calls.
            read_timeout=300,
            write_timeout=300,
            connect_timeout=60,
            pool_timeout=60,
        )
    except TimedOut:
        logger.exception("Calendar PDF upload timed out for user_id=%s", user.id)
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text="⏳ ارسال فایل PDF زمان‌بر شد. لطفاً چند لحظه بعد دوباره تلاش کنید.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30,
            )
        except Exception:
            logger.exception("Failed to send calendar PDF timeout message for user_id=%s", user.id)
    except Exception:
        logger.exception("Calendar PDF generation/upload failed for user_id=%s", user.id)
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text="❌ در ایجاد یا ارسال PDF تقویم مشکلی پیش آمد. لطفاً دوباره تلاش کنید.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30,
            )
        except Exception:
            logger.exception("Failed to send calendar PDF error message for user_id=%s", user.id)
