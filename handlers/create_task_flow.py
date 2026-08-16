"""Small runtime patch layer for the shared manual create-task flow.

The repository already centralizes the create-task state machine in handlers.task.
This module only adds cross-cutting guards/UI without changing unrelated handlers.
"""

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


def install_create_task_flow(task_module) -> None:
    """Install minimal guards/UI around the existing shared task flow."""
    if getattr(task_module, "_create_task_flow_guards_installed", False):
        return
    task_module._create_task_flow_guards_installed = True

    # 1) Every entry (including /add) starts from a clean draft and exposes Cancel.
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

    # main.py imports handlers.task.add_task/save_task before install_tag_flow runs.
    # Refresh those bindings while the application is being constructed.
    import sys
    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.add_task = shared_add_task

    # 2) Add Cancel to all task-flow keyboards that are built in handlers.task.
    original_skip_keyboard = task_module._skip_keyboard

    def skip_keyboard_with_cancel(callback_data):
        return add_create_cancel(original_skip_keyboard(callback_data))

    task_module._skip_keyboard = skip_keyboard_with_cancel

    original_category_keyboard = task_module._category_keyboard

    async def category_keyboard_with_cancel(user_id):
        return add_create_cancel(await original_category_keyboard(user_id))

    task_module._category_keyboard = category_keyboard_with_cancel

    for name in ("priority_keyboard", "deadline_keyboard"):
        original_keyboard = getattr(task_module, name)

        def wrapped_keyboard(original=original_keyboard):
            return add_create_cancel(original())

        setattr(task_module, name, wrapped_keyboard)

    # The smart tag flow replaces _ask_tags/_ask_assignment and uses these helpers
    # from tag_suggestions_legacy, so patch their module-level builders as well.
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
        # The base task flow remains usable even if the optional smart-tag layer is absent.
        pass

    # 3) Validate Title at the input step without touching save_task's dispatcher order.
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
        return await original_save_task(update, context)

    task_module.save_task = save_task_with_create_validation
    if main_module is not None:
        main_module.save_task = save_task_with_create_validation

    # 4) Validate and guard the final confirmation. The guard is intentionally on
    # assignment_callback because both safe_assignment_confirm and the existing
    # callback registration converge there.
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
