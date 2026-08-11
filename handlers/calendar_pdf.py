from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import ContextTypes

from services.calendar_pdf_service import build_calendar_pdf
from services.pdf_runtime import render_pdf_in_worker, warm_pdf_fonts
from services.task_service import get_active_tasks_async

logger = logging.getLogger(__name__)
warm_pdf_fonts()


async def _safe_callback_answer(query) -> None:
    try:
        await query.answer(read_timeout=2, write_timeout=2, connect_timeout=2, pool_timeout=2)
    except (BadRequest, TimedOut):
        logger.debug("Could not acknowledge calendar PDF callback", exc_info=True)


async def _edit_status(message, text: str) -> None:
    try:
        await message.edit_text(text)
    except (BadRequest, TimedOut):
        logger.debug("Could not edit calendar PDF status message", exc_info=True)


async def _send_calendar_pdf(message, pdf) -> None:
    pdf.seek(0)
    payload = pdf.getvalue()
    if not payload:
        raise RuntimeError("Monthly calendar PDF buffer is empty")

    last_error = None
    for attempt in range(1, 4):
        try:
            await message.reply_document(
                document=payload,
                filename="jalali-monthly-calendar.pdf",
                caption="📅 تقویم ماهانه شمسی آماده است.",
                disable_content_type_detection=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=30,
                pool_timeout=30,
            )
            return
        except (NetworkError, TimedOut) as exc:
            last_error = exc
            if attempt >= 3:
                raise
            logger.warning("Monthly calendar PDF upload failed (attempt %s/3): %s", attempt, exc)
            await asyncio.sleep(attempt * 2)

    if last_error is not None:
        raise last_error


async def calendar_pdf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_callback_answer(query)
    user_id = update.effective_user.id
    status_message = await query.message.reply_text("⏳ در حال تولید فایل PDF تقویم ماهانه، لطفاً شکیبا باشید...")
    pdf = None
    try:
        tasks = await get_active_tasks_async(user_id)
        pdf = await render_pdf_in_worker(build_calendar_pdf, tasks, user_id)
        logger.info("Monthly calendar PDF rendered user=%s size=%d bytes", user_id, pdf.getbuffer().nbytes)
        await _send_calendar_pdf(query.message, pdf)
        await _edit_status(status_message, "✅ فایل PDF تقویم ماهانه با موفقیت تولید و ارسال شد.")
    except asyncio.TimeoutError:
        logger.exception("Jalali calendar PDF render timed out user=%s", user_id)
        await _edit_status(status_message, "❌ تولید فایل PDF تقویم بیش از حد طول کشید. لطفاً دوباره تلاش کنید.")
    except (NetworkError, TimedOut):
        logger.exception("Jalali calendar PDF upload failed user=%s", user_id)
        await _edit_status(status_message, "❌ ارسال فایل PDF به تلگرام ناموفق بود. احتمالاً اتصال واسط شبکه فایل را قطع کرده است.")
    except Exception:
        logger.exception("Jalali calendar PDF generation failed user=%s", user_id)
        await _edit_status(status_message, "❌ خطایی در ساخت فایل PDF تقویم ماهانه رخ داد.")
    finally:
        if pdf is not None:
            pdf.close()
