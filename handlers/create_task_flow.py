"""Small runtime patch layer for the shared manual create-task flow.

The repository already centralizes the create-task state machine in handlers.task.
This module only adds cross-cutting guards/UI without changing unrelated handlers.
"""

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


CREATE_CANCEL_CALLBACK = "assign_cancel_create"
CREATE_CANCEL_LABEL = "❌ لغو ایجاد تسک"
_VALID_PRIORITIES = {"high", "medium", "low"}


def _cancel_button():
    return InlineKeyboardButton(CREATE_CANCEL_LABEL, callback_data=CREATE_CANCEL_CALLBACK)


def add_create_cancel(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Return a copy of a create-task keyboard with a single cancel action."""
    rows = [list(row) for row in (markup.inline_keyboard if markup else [])]
    if not any(button.callback_data == CREATE_CANCEL_CALLBACK for row in rows for button in row):
        rows.append([_cancel_button()])
    return InlineKeyboardMarkup(rows)


def validate_create_task_draft(task: dict) -> str | None:
    """Single source of truth for the final create-task draft checks."""
    title = str(task.get("title") or "").strip()
    if not title:
        return "عنوان تسک نمی‌تواند خالی باشد."
    if len(title) > 200:
        return "عنوان تسک نباید بیشتر از ۲۰۰ کاراکتر باشد."
    if task.get("priority") not in _VALID_PRIORITIES:
        return "اولویت تسک نامعتبر است."
    return None


def clear_create_task_state(context) -> None:
    """Clear only state owned by create-task flow; preserve unrelated feature state."""
    context.user_data.pop("new_task", None)
    context.user_data.pop("step", None)
    context.user_data.pop("tag_suggestions", None)
    context.user_data.pop("awaiting_tag_input", None)
    context.user_data.pop("create_task_finalizing", None)
    context.user_data.pop("create_task_message_id", None)


def _rich_button(text: str, callback_data: str, style: str = "primary") -> str:
    """Build a Telegram Rich HTML callback button with safe visible text."""
    return (
        f'<tg-button type="callback_data" style="{style}" '
        f'data="{escape(callback_data, quote=True)}">{escape(text)}</tg-button>'
    )


def _rich_rows(buttons: list[str], per_row: int = 2) -> str:
    rows = []
    for index in range(0, len(buttons), per_row):
        row = "".join(buttons[index:index + per_row])
        rows.append(f'<tg-button-row align="center">{row}</tg-button-row>')
    return "".join(rows)


async def _send_priority_rich_message(message, bot, context=None) -> None:
    """Send the priority step as a Telegram Rich Message with embedded buttons."""
    rich_html = (
        "<p>🎯 اولویت را انتخاب کنید:</p>"
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="danger" data="priority_high">🔴 بالا</tg-button>'
        '<tg-button type="callback_data" style="primary" data="priority_medium">🟠 متوسط</tg-button>'
        '<tg-button type="callback_data" style="success" data="priority_low">🟢 پایین</tg-button>'
        "</tg-button-row>"
        '<tg-button-row align="center">'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )
    sent = await bot._post(
        "sendRichMessage",
        data={
            "chat_id": message.chat_id,
            "rich_message": {"html": rich_html, "is_rtl": True},
        },
    )
    if context is not None and getattr(sent, "message_id", None):
        context.user_data["create_task_message_id"] = sent.message_id


async def _edit_create_rich_message(context, fallback_message, rich_html: str) -> bool:
    """Edit the single create-task Rich Message instead of sending another prompt."""
    message_id = context.user_data.get("create_task_message_id")
    if not message_id:
        return False
    chat_id = getattr(fallback_message, "chat_id", None)
    if not chat_id:
        return False
    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "rich_message": {"html": rich_html, "is_rtl": True},
        },
    )
    return True


async def _show_category_rich_message(task_module, message, context, user_id) -> None:
    """Render category choices as Rich Message buttons, reusing the current message."""
    categories = await task_module._category_options(user_id)
    buttons = [
        _rich_button(f"📂 {category}", f"category_pick_{index}")
        for index, category in enumerate(categories)
    ]
    buttons.append(_rich_button("⏭ رد کردن", "category_skip", "primary"))
    buttons.append(_rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link"))
    rich_html = "<p>📂 دسته‌بندی را انتخاب کنید یا نام دسته‌بندی جدید را همین‌جا ارسال کنید.</p>" + _rich_rows(buttons)
    if not await _edit_create_rich_message(context, message, rich_html):
        sent = await context.bot._post(
            "sendRichMessage",
            data={
                "chat_id": message.chat_id,
                "rich_message": {"html": rich_html, "is_rtl": True},
            },
        )
        if getattr(sent, "message_id", None):
            context.user_data["create_task_message_id"] = sent.message_id


async def _show_tags_rich_message(message, context) -> None:
    """Render tag suggestions as Rich Message buttons, reusing the current message."""
    from handlers import tag_suggestions_legacy as legacy

    user = getattr(message, "from_user", None)
    user_id = getattr(user, "id", 0)
    keyboard, tags = await legacy.recent_tag_keyboard(user_id, limit=3)
    del keyboard
    context.user_data["tag_suggestions"] = tags

    buttons = [
        _rich_button(f"🏷 {tag}", f"tag_pick_{index}")
        for index, tag in enumerate(tags)
    ]
    buttons.append(_rich_button("➕ تگ جدید", "tag_new"))
    buttons.append(_rich_button("⏭ رد کردن", "tags_skip"))
    buttons.append(_rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link"))
    rich_html = "<p>🏷 تگ را انتخاب کنید یا تگ جدید را وارد کنید:</p>" + _rich_rows(buttons)
    if not await _edit_create_rich_message(context, message, rich_html):
        sent = await context.bot._post(
            "sendRichMessage",
            data={
                "chat_id": message.chat_id,
                "rich_message": {"html": rich_html, "is_rtl": True},
            },
        )
        if getattr(sent, "message_id", None):
            context.user_data["create_task_message_id"] = sent.message_id


async def _show_description_in_current_message(message, context) -> None:
    """Move to the next text step in the same message when possible."""
    rich_html = (
        "<p>📄 توضیح / یادداشت را وارد کنید یا دکمه «رد کردن» را بزنید:</p>"
        "<p>(اختیاری)</p>"
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="primary" data="description_skip">⏭ رد کردن</tg-button>'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )
    if not await _edit_create_rich_message(context, message, rich_html):
        await message.reply_text("📄 توضیح / یادداشت را وارد کنید یا دکمه «رد کردن» را بزنید:\n(اختیاری)")


def install_create_task_flow(task_module) -> None:
    """Install minimal guards/UI around the existing shared task flow."""
    if getattr(task_module, "_create_task_flow_guards_installed", False):
        return
    task_module._create_task_flow_guards_installed = True

    async def shared_add_task(update, context):
        clear_create_task_state(context)
        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"
        message = update.effective_message or update.callback_query.message
        await message.reply_text(
            "📝 عنوان تسک را وارد کنید:",
            reply_markup=add_create_cancel(InlineKeyboardMarkup([])),
        )

    task_module.add_task = shared_add_task

    import sys
    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.add_task = shared_add_task

    original_skip_keyboard = task_module._skip_keyboard

    def skip_keyboard_with_cancel(callback_data):
        return add_create_cancel(original_skip_keyboard(callback_data))

    task_module._skip_keyboard = skip_keyboard_with_cancel

    original_category_keyboard = task_module._category_keyboard

    async def category_keyboard_with_cancel(user_id):
        return add_create_cancel(await original_category_keyboard(user_id))

    task_module._category_keyboard = category_keyboard_with_cancel

    original_priority_keyboard = task_module.priority_keyboard

    def priority_keyboard_with_cancel(*args, **kwargs):
        return add_create_cancel(original_priority_keyboard(*args, **kwargs))

    task_module.priority_keyboard = priority_keyboard_with_cancel

    original_deadline_keyboard = task_module.deadline_keyboard

    def deadline_keyboard_with_cancel(*args, **kwargs):
        return add_create_cancel(original_deadline_keyboard(*args, **kwargs))

    task_module.deadline_keyboard = deadline_keyboard_with_cancel

    try:
        import handlers.tag_suggestions_legacy as legacy

        original_recent_tag_keyboard = legacy.recent_tag_keyboard

        async def recent_tag_keyboard_with_cancel(*args, **kwargs):
            markup, tags = await original_recent_tag_keyboard(*args, **kwargs)
            return add_create_cancel(markup), tags

        legacy.recent_tag_keyboard = recent_tag_keyboard_with_cancel
        legacy.assignment_grid_keyboard = lambda *args, **kwargs: add_create_cancel(
            __import__("utils.keyboard", fromlist=["assignment_grid_keyboard"]).assignment_grid_keyboard(*args, **kwargs)
        )
    except Exception:
        pass

    original_ask_category = task_module._ask_category
    original_ask_tags = getattr(task_module, "_ask_tags", None)
    original_ask_description = getattr(task_module, "_ask_description", None)

    async def ask_category_rich(message, context, user_id):
        context.user_data["step"] = "category"
        await _show_category_rich_message(task_module, message, context, user_id)

    async def ask_tags_rich(message, context):
        context.user_data["step"] = "tags"
        await _show_tags_rich_message(message, context)

    async def ask_description_same_message(message, context):
        context.user_data["step"] = "description"
        await _show_description_in_current_message(message, context)

    task_module._ask_category = ask_category_rich
    task_module._ask_tags = ask_tags_rich
    task_module._ask_description = ask_description_same_message

    original_save_task = task_module.save_task

    async def save_task_with_create_validation(update, context):
        if context.user_data.get("step") == "title":
            task = context.user_data.setdefault("new_task", {})
            title = str(update.effective_message.text or "").strip()
            if not title:
                await update.effective_message.reply_text("⚠️ عنوان تسک نمی‌تواند خالی باشد.")
                return
            if len(title) > 200:
                await update.effective_message.reply_text("⚠️ عنوان تسک نباید بیشتر از ۲۰۰ کاراکتر باشد.")
                return
            task["title"] = title
            context.user_data["step"] = "priority"
            await _send_priority_rich_message(update.effective_message, context.bot, context)
            return
        return await original_save_task(update, context)

    task_module.save_task = save_task_with_create_validation
    if main_module is not None:
        main_module.save_task = save_task_with_create_validation

    original_assignment_callback = task_module.assignment_callback

    async def assignment_callback_with_guard(update, context):
        query = update.callback_query
        data = query.data or ""
        if data == CREATE_CANCEL_CALLBACK:
            clear_create_task_state(context)
            await query.answer()
            await query.message.reply_text("❌ ایجاد تسک لغو شد.")
            return
        if data == "assign_confirm_create":
            task = context.user_data.get("new_task")
            if not isinstance(task, dict):
                await query.answer("فرایند ایجاد تسک منقضی شده است.", show_alert=True)
                return
            error = validate_create_task_draft(task)
            if error:
                await query.answer(error, show_alert=True)
                return
            if task.get("create_task_finalizing"):
                await query.answer("ثبت تسک در حال انجام است.", show_alert=True)
                return
            task["create_task_finalizing"] = True
        return await original_assignment_callback(update, context)

    task_module.assignment_callback = assignment_callback_with_guard
    if main_module is not None:
        main_module.assignment_callback = assignment_callback_with_guard
