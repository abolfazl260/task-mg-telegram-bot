from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import (
    get_active_tasks_async,
    get_unassigned_tasks_async,
    get_task_dashboard_counts_async,
    user_can_modify_task_async,
)
from handlers.task import (
    PAGE_SIZE,
    build_detail_table,
    format_task_card,
    sort_tasks,
    _task_details_keyboard,
)


def tasks_view_menu_keyboard():
    """First screen for /tasks: filter menu only; task cards are never dumped here."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 فهرست کل وظایف", callback_data="view_tasks_all")],
        [
            InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="view_tasks_priority"),
            InlineKeyboardButton("📊 وضعیت تسک‌ها", callback_data="view_tasks_status"),
        ],
        [
            InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="view_tasks_category"),
            InlineKeyboardButton("🏷 بر اساس تگ", callback_data="view_tasks_tag"),
        ],
        [
            InlineKeyboardButton("👤 بر اساس مسئول", callback_data="view_tasks_assignee"),
            InlineKeyboardButton("☀️ برنامه امروز", callback_data="view_tasks_today"),
        ],
    ])


async def paginated_list_tasks(update, context):
    """Handle /tasks by showing the dynamic mini dashboard and filter menu only."""
    context.user_data.pop("tasks_filter", None)
    context.user_data.pop("tasks_filter_options", None)
    stats = await get_task_dashboard_counts_async(update.effective_user.id)

    text = (
        "📊 خلاصه وضعیت شما\n"
        f"🔹 تسک‌های در جریان: {stats['count_active']}\n"
        f"☀️ برنامه امروز: {stats['count_today']} تسک\n"
        f"🔥 عقب‌افتاده: {stats['count_overdue']} وظیفه (نیاز به پیگیری!)\n\n"
        "👇 برای مشاهده لیست و مدیریت کارها، یک گزینه را انتخاب کنید:"
    )

    await update.effective_message.reply_text(
        text,
        reply_markup=tasks_view_menu_keyboard(),
    )


def _unique_values(tasks, field):
    values = []
    seen = set()
    for task in tasks:
        raw = task.get(field)
        if isinstance(raw, str):
            parts = [p.strip().lstrip("#") for p in raw.replace("،", ",").replace("\n", ",").split(",")]
        else:
            parts = [str(raw).strip()] if raw else []
        for value in parts:
            if not value:
                continue
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                values.append(value)
    return values


async def _show_filter_choices(update, context, kind):
    """Show a second-level selector using short index-based callback_data."""
    query = update.callback_query
    await query.answer()
    tasks = await get_active_tasks_async(update.effective_user.id)
    if not tasks:
        await query.edit_message_text("🎉 تسک فعالی ندارید.")
        return

    if kind == "priority":
        options = [("🔴 بالا", "high"), ("🟠 متوسط", "medium"), ("🟢 پایین", "low")]
        title = "🎯 اولویت موردنظر را انتخاب کنید:"
    elif kind == "status":
        options = [
            ("⏳ در انتظار", "pending"),
            ("🚀 در حال انجام", "in_progress"),
            ("✅ انجام شده", "done"),
            ("❌ لغو شده", "cancelled"),
        ]
        title = "📊 وضعیت موردنظر را انتخاب کنید:"
    elif kind == "category":
        values = _unique_values(tasks, "category")[:20]
        options = [(f"📂 {value}", value) for value in values]
        title = "📂 دسته‌بندی موردنظر را انتخاب کنید:"
    elif kind == "tag":
        values = _unique_values(tasks, "tags")[:20]
        options = [(f"🏷 {value}", value) for value in values]
        title = "🏷 تگ موردنظر را انتخاب کنید:"
    elif kind == "assignee":
        assignees = []
        seen = set()
        for task in tasks:
            value = (task.get("assignee") or "").strip()
            if not value:
                value = "none"
            if value not in seen:
                seen.add(value)
                assignees.append(value)
        options = [("⏭ بدون مسئول" if value == "none" else f"👤 {value}", value) for value in assignees[:20]]
        title = "👤 مسئول موردنظر را انتخاب کنید:"
    else:
        return

    if not options:
        await query.edit_message_text("موردی برای این فیلتر پیدا نشد.")
        return

    context.user_data.setdefault("tasks_filter_options", {})[kind] = [value for _, value in options]

    rows = []
    for index in range(0, len(options), 2):
        row = []
        for option_index, (label, _value) in enumerate(options[index:index + 2], start=index):
            row.append(InlineKeyboardButton(label[:30], callback_data=f"tasks_filter_{kind}_{option_index}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت به فیلترها", callback_data="view_tasks_menu")])
    await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(rows))


async def tasks_view_callback(update, context):
    """Dispatch the initial /tasks menu and its filter choices."""
    query = update.callback_query
    data = query.data or ""

    if data == "view_tasks_menu":
        await query.answer()
        await query.edit_message_text(
            "📋 **نحوه نمایش وظایف را انتخاب کنید:**",
            reply_markup=tasks_view_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    if data == "view_tasks_all":
        await query.answer()
        context.user_data["tasks_filter"] = {"type": "all"}
        await _render_page(update, context, page=1, sort_key="deadline", edit=False)
        return

    if data == "view_tasks_today":
        await query.answer()
        context.user_data["tasks_filter"] = {"type": "today"}
        await _render_filtered(update, context, "today", None)
        return

    for kind in ("priority", "status", "category", "tag", "assignee"):
        if data == f"view_tasks_{kind}":
            await _show_filter_choices(update, context, kind)
            return

    if data.startswith("tasks_filter_"):
        remainder = data[len("tasks_filter_"):]
        try:
            kind, index_text = remainder.rsplit("_", 1)
            index = int(index_text)
        except (ValueError, TypeError):
            await query.answer("گزینه فیلتر نامعتبر است.", show_alert=True)
            return

        if kind not in ("priority", "status", "category", "tag", "assignee"):
            return

        values = context.user_data.get("tasks_filter_options", {}).get(kind, [])
        if index < 0 or index >= len(values):
            await query.answer("این گزینه منقضی شده است؛ دوباره فیلتر را انتخاب کنید.", show_alert=True)
            return

        value = values[index]
        await query.answer()
        context.user_data["tasks_filter"] = {"type": kind, "value": value}
        await _render_filtered(update, context, kind, value)
        return


async def _render_filtered(update, context, kind, value):
    tasks = await get_active_tasks_async(update.effective_user.id)
    if kind == "today":
        import datetime as _dt
        today = _dt.datetime.now().strftime("%Y-%m-%d")
        tasks = [t for t in tasks if str(t.get("deadline") or "")[:10] == today]
    elif kind == "priority":
        tasks = [t for t in tasks if t.get("priority") == value]
    elif kind == "status":
        tasks = [t for t in tasks if t.get("status", "pending") == value]
    elif kind == "category":
        tasks = [t for t in tasks if (t.get("category") or "").strip() == value]
    elif kind == "tag":
        tasks = [t for t in tasks if value.casefold() in {
            p.strip().lstrip("#").casefold()
            for p in str(t.get("tags") or "").replace("،", ",").replace("\n", ",").split(",")
            if p.strip()
        }]
    elif kind == "assignee":
        tasks = [t for t in tasks if ((t.get("assignee") or "").strip() or "none") == value]

    if not tasks:
        await update.effective_message.reply_text("🔎 برای این فیلتر تسکی پیدا نشد.")
        return

    tasks = sort_tasks(tasks, "deadline")
    total = len(tasks)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page_tasks = tasks[:PAGE_SIZE]
    text = build_detail_table(page_tasks, start_index=1) + f"\n\n📄 صفحه 1 از {total_pages}"
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")],
        [InlineKeyboardButton("🔙 انتخاب فیلتر دیگر", callback_data="view_tasks_menu")],
    ]))
    profile = context.bot_data.get("bot_config")
    for task in page_tasks:
        can_mod = await user_can_modify_task_async(update.effective_user.id, task)
        reply_markup = (
            __import__("utils.keyboard", fromlist=["task_action_keyboard"]).task_action_keyboard(
                task.get("id", ""), task.get("status", "pending"), profile
            ) if can_mod else _task_details_keyboard(task.get("id", ""))
        )
        await update.effective_message.reply_text(
            await format_task_card(task),
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


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
