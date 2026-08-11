from __future__ import annotations

from io import BytesIO

from services.calendar_pdf_service import build_calendar_pdf
from services.task_service import get_all_user_tasks


async def calendar_pdf_callback(update, context):
    """Send the single canonical monthly calendar PDF renderer to the user."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    tasks = get_all_user_tasks(user.id)
    pdf_buffer = build_calendar_pdf(tasks, user.id)
    filename = "تقویم-ماهانه.pdf"
    pdf_buffer.name = filename

    await context.bot.send_document(
        chat_id=chat.id,
        document=pdf_buffer,
        filename=filename,
        caption="📅 تقویم ماهانه تسک‌ها",
    )
