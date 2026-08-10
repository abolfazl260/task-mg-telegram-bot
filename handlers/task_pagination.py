from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import (
    get_active_tasks_async,
    get_unassigned_tasks_async,
    user_can_modify_task_async,
)
from handlers.task import (
    PAGE_SIZE,
    build_detail_table,
    format_task_card,
    sort_tasks,
    _task_details_keyboard,
)


async def paginated_list_tasks(update, context):
    sort_key = context.user_data.get("tasks_sort", "deadline")
    await _render_page(update, context, page=1, sort_key=sort_key, edit=False)


async def paginated_sort_callback(update, context):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("sort_", "")
    if key not in ("deadline", "priority", "created"):
        key = "deadline"
    context.user_data["tasks_sort"] = key
    await _render_page(update, context, page=1, sort_key=key, edit=False)


async def paginated_detail_page(update, context):
    query = update.callback_query
    await query.answer()
    try:
        page = max(1, int(query.data.replace("detail_page_", "")))
    except ValueError:
        page = 1
    sort_key = context.user_data.get("tasks_sort", "deadline")
    await _render_page(update, context, page=page, sort_key=sort_key, edit=True)


async def _render_page(update, context, page, sort_key, edit):
    tasks = await get_active_tasks_async(update.effective_user.id)
    if not tasks:
        await update.effective_message.reply_text("🎉 تسک فعال ندارید")
        return
    tasks = sort_tasks(tasks, sort_key)
    total = len(tasks)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    page_tasks = tasks[start:start + PAGE_SIZE]
    text = build_detail_table(page_tasks, start_index=start + 1) + f"\n\n📄 صفحه {page} از {total_pages}"
    keyboard = [[
        InlineKeyboardButton("📅 ددلاین", callback_data="sort_deadline"),
        InlineKeyboardButton("🎯 اولویت", callback_data="sort_priority"),
        InlineKeyboardButton("🕐 ایجاد", callback_data="sort_created"),
    ]]
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"detail_page_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"detail_page_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")])
    message = update.effective_message
    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    for task in page_tasks:
        can_mod = await user_can_modify_task_async(update.effective_user.id, task)
        reply_markup = (
            __import__("utils.keyboard", fromlist=["task_action_keyboard"]).task_action_keyboard(
                task.get("id", ""), task.get("status", "pending"), context.bot_data.get("bot_config")
            ) if can_mod else _task_details_keyboard(task.get("id", ""))
        )
        # format_task_card is an async adapter after the calendar runtime patch
        # in main.py; await it before passing the rendered text to Telegram.
        card_text = await format_task_card(task)
        await message.reply_text(card_text, reply_markup=reply_markup, parse_mode="Markdown")


async def _full_unassigned_tasks(update, context):
    tasks = sort_tasks(await get_unassigned_tasks_async(update.effective_user.id), "created")
    if not tasks:
        await update.effective_message.reply_text("وظیفه بدون مسئول ندارید.")
        return
    offset = context.user_data.get("unassigned_offset", 0)
    if offset >= len(tasks):
        offset = 0
    page_tasks = tasks[offset:offset + PAGE_SIZE]
    context.user_data["unassigned_offset"] = offset + len(page_tasks)
    total_pages = max(1, (len(tasks) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = offset // PAGE_SIZE + 1
    await update.effective_message.reply_text(
        f"📋 وظایف بدون مسئول: {len(tasks)} مورد\n📄 صفحه {page} از {total_pages}\nنمایش {offset + 1} تا {offset + len(page_tasks)}."
    )
    profile = context.bot_data.get("bot_config")
    for task in page_tasks:
        card_text = await format_task_card(task)
        await update.effective_message.reply_text(
            card_text,
            reply_markup=__import__("utils.keyboard", fromlist=["task_action_keyboard"]).task_action_keyboard(task.get("id", ""), task.get("status", "pending"), profile),
            parse_mode="Markdown",
        )
    remaining = len(tasks) - context.user_data["unassigned_offset"]
    if remaining > 0:
        await update.effective_message.reply_text(f"➡️ {remaining} وظیفه دیگر باقی مانده است.\nبرای دیدن سری بعدی دوباره /unassigned را انتخاب کنید.")
    else:
        context.user_data["unassigned_offset"] = 0
        await update.effective_message.reply_text("✅ همه وظایف بدون مسئول نمایش داده شد.")


import handlers.task as _task_handler
_task_handler.unassigned_tasks.__code__ = _full_unassigned_tasks.__code__
