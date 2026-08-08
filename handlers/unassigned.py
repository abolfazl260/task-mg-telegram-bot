from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationHandlerStop

from services.task_service import get_unassigned_tasks
from handlers.task import PAGE_SIZE, format_task_card, sort_tasks
from utils.keyboard import task_action_keyboard


async def unassigned_tasks_full(update, context):
    """Show unassigned tasks with the same complete action keyboard as normal tasks."""
    tasks = sort_tasks(get_unassigned_tasks(update.effective_user.id), "created")
    if not tasks:
        await update.effective_message.reply_text("وظیفه بدون مسئول ندارید.")
        raise ApplicationHandlerStop

    offset = context.user_data.get("unassigned_offset", 0)
    if offset >= len(tasks):
        offset = 0

    page_tasks = tasks[offset:offset + PAGE_SIZE]
    context.user_data["unassigned_offset"] = offset + len(page_tasks)
    total_pages = max(1, (len(tasks) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = offset // PAGE_SIZE + 1

    await update.effective_message.reply_text(
        f"📋 وظایف بدون مسئول: {len(tasks)} مورد\n"
        f"📄 صفحه {page} از {total_pages}\n"
        f"نمایش {offset + 1} تا {offset + len(page_tasks)}."
    )

    profile = context.bot_data.get("bot_config")
    for task in page_tasks:
        await update.effective_message.reply_text(
            format_task_card(task),
            reply_markup=task_action_keyboard(
                task.get("id", ""),
                task.get("status", "pending"),
                profile,
            ),
            parse_mode="Markdown",
        )

    remaining = len(tasks) - context.user_data["unassigned_offset"]
    if remaining > 0:
        await update.effective_message.reply_text(
            f"➡️ {remaining} وظیفه دیگر باقی مانده است.\n"
            "برای دیدن سری بعدی دوباره /unassigned را انتخاب کنید."
        )
    else:
        context.user_data["unassigned_offset"] = 0
        await update.effective_message.reply_text("✅ همه وظایف بدون مسئول نمایش داده شد.")

    raise ApplicationHandlerStop
