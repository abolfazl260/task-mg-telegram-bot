"""Runtime patch layer for the manual create-task flow."""

from datetime import datetime, timedelta
from html import escape

import jdatetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CREATE_CANCEL_CALLBACK = "assign_cancel_create"
CREATE_CANCEL_LABEL = "❌ لغو ایجاد تسک"
_VALID_PRIORITIES = {"high", "medium", "low"}


def _cancel_button():
    return InlineKeyboardButton(CREATE_CANCEL_LABEL, callback_data=CREATE_CANCEL_CALLBACK)


def add_create_cancel(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    rows = [list(row) for row in (markup.inline_keyboard if markup else [])]
    if not any(button.callback_data == CREATE_CANCEL_CALLBACK for row in rows for button in row):
        rows.append([_cancel_button()])
    return InlineKeyboardMarkup(rows)


def validate_create_task_draft(task: dict) -> str | None:
    title = str(task.get("title") or "").strip()
    if not title:
        return "عنوان تسک نمی‌تواند خالی باشد."
    if len(title) > 200:
        return "عنوان تسک نباید بیشتر از ۲۰۰ کاراکتر باشد."
    if task.get("priority") not in _VALID_PRIORITIES:
        return "اولویت تسک نامعتبر است."
    return None


def clear_create_task_state(context) -> None:
    for key in (
        "new_task", "step", "tag_suggestions", "awaiting_tag_input",
        "create_task_finalizing", "create_task_message_id", "create_task_user_id",
        "_create_selected_team_id",
    ):
        context.user_data.pop(key, None)


def _rich_button(text: str, callback_data: str, style: str = "primary") -> str:
    return (
        f'<tg-button type="callback_data" style="{style}" '
        f'data="{escape(callback_data, quote=True)}">{escape(text)}</tg-button>'
    )


def _rich_rows(buttons: list[str], per_row: int = 2) -> str:
    return "".join(
        f'<tg-button-row align="center">{"".join(buttons[i:i + per_row])}</tg-button-row>'
        for i in range(0, len(buttons), per_row)
    )


async def _send_create_rich_message(message, bot, context) -> None:
    html = (
        '<p><b>📝 ایجاد تسک جدید</b></p>'
        "<p>عنوان تسک را در پیام بعدی ارسال کنید.</p>"
        '<tg-button-row align="center">'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )
    sent = await bot._post("sendRichMessage", data={
        "chat_id": message.chat_id,
        "rich_message": {"html": html, "is_rtl": True},
    })
    if getattr(sent, "message_id", None):
        context.user_data["create_task_message_id"] = sent.message_id


async def _edit_create_rich_message(context, fallback_message, rich_html: str) -> bool:
    message_id = context.user_data.get("create_task_message_id")
    chat_id = getattr(fallback_message, "chat_id", None)
    if not message_id or not chat_id:
        return False
    await context.bot._post("editMessageText", data={
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": {"html": rich_html, "is_rtl": True},
    })
    return True


def _priority_html() -> str:
    return (
        '<p><b>🎯 اولویت تسک</b></p><p>اولویت مناسب را انتخاب کنید:</p>'
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="danger" data="priority_high">🔴 بالا</tg-button>'
        '<tg-button type="callback_data" style="primary" data="priority_medium">🟠 متوسط</tg-button>'
        '<tg-button type="callback_data" style="success" data="priority_low">🟢 پایین</tg-button>'
        "</tg-button-row>"
        '<tg-button-row align="center">'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )


def _deadline_label(days: int) -> str:
    target = datetime.now().date() + timedelta(days=days)
    jalali = jdatetime.date.fromgregorian(date=target).strftime("%m/%d")
    prefix = "امروز" if days == 0 else "فردا" if days == 1 else f"+{days} روز"
    return f"{prefix} — {jalali}"


def _deadline_html() -> str:
    dates = [
        _rich_button(f"📌 {_deadline_label(0)}", "deadline_0", "success"),
        _rich_button(f"📌 {_deadline_label(1)}", "deadline_1", "primary"),
        _rich_button(f"📅 {_deadline_label(2)}", "deadline_2"),
        _rich_button(f"📅 {_deadline_label(3)}", "deadline_3"),
        _rich_button(f"📅 {_deadline_label(4)}", "deadline_4"),
        _rich_button(f"📅 {_deadline_label(5)}", "deadline_5"),
        _rich_button(f"📅 {_deadline_label(6)}", "deadline_6"),
        _rich_button(f"📅 {_deadline_label(7)}", "deadline_7"),
    ]
    actions = [
        _rich_button("🕐 تاریخ و زمان دلخواه", "deadline_custom", "primary"),
        _rich_button("⏭ بدون زمان‌بندی", "deadline_none"),
        _rich_button("🔙 مرحله قبل", "step_back_priority"),
        _rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link"),
    ]
    return '<p><b>📅 زمان انجام تسک</b></p><p>زمان موردنظر را انتخاب کنید:</p>' + _rich_rows(dates) + _rich_rows(actions)


async def _show_category_rich_message(task_module, message, context, user_id) -> None:
    categories = await task_module._category_options(user_id)
    buttons = [_rich_button(f"📂 {category}", f"category_pick_{i}") for i, category in enumerate(categories)]
    buttons += [_rich_button("⏭ بدون دسته‌بندی", "category_skip"), _rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")]
    html = '<p><b>📂 دسته‌بندی</b></p><p>یک دسته‌بندی را انتخاب کنید یا نام دسته‌بندی جدید را ارسال کنید.</p>' + _rich_rows(buttons)
    if not await _edit_create_rich_message(context, message, html):
        raise RuntimeError("create-task Rich Message is not initialized")


async def _show_tags_rich_message(message, context) -> None:
    from handlers import tag_suggestions_legacy as legacy
    user_id = context.user_data.get("create_task_user_id") or getattr(getattr(message, "from_user", None), "id", 0)
    _, tags = await legacy.recent_tag_keyboard(user_id, limit=3)
    context.user_data["tag_suggestions"] = tags
    buttons = [_rich_button(f"🏷 {tag}", f"tag_pick_{i}") for i, tag in enumerate(tags)]
    buttons += [_rich_button("➕ تگ جدید", "tag_new", "success"), _rich_button("⏭ بدون تگ", "tags_skip"), _rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")]
    html = '<p><b>🏷 تگ‌های تسک</b></p><p>تگ پیشنهادی را انتخاب کنید یا تگ جدید وارد کنید.</p>' + _rich_rows(buttons)
    if not await _edit_create_rich_message(context, message, html):
        raise RuntimeError("create-task Rich Message is not initialized")


async def _show_description_rich_message(message, context) -> None:
    html = (
        '<p><b>📄 توضیحات تسک</b></p><p>توضیح یا یادداشت را ارسال کنید. این بخش اختیاری است.</p>'
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="primary" data="description_skip">⏭ رد کردن</tg-button>'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )
    if not await _edit_create_rich_message(context, message, html):
        raise RuntimeError("create-task Rich Message is not initialized")


async def _show_assignment_rich_message(message, context) -> None:
    html = (
        '<p><b>👤 انتخاب مسئول تسک</b></p><p>تسک را به چه کسی اختصاص می‌دهید؟</p>'
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="success" data="assign_self">🙋‍♂️ خودم</tg-button>'
        '<tg-button type="callback_data" style="primary" data="assign_teams">👥 هم‌تیمی‌ها</tg-button>'
        "</tg-button-row>"
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="primary" data="assign_search">🔎 جستجوی کاربر</tg-button>'
        '<tg-button type="callback_data" data="assign_none">⏭ بدون مسئول</tg-button>'
        "</tg-button-row>"
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="link" data="step_back_tags">🔙 مرحله قبل</tg-button>'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )
    if not await _edit_create_rich_message(context, message, html):
        raise RuntimeError("create-task Rich Message is not initialized")


async def _show_assignment_summary_rich(query, context) -> None:
    task = context.user_data.setdefault("new_task", {})
    assignee = task.get("assignee")
    name = (assignee.get("display_name") or assignee.get("username") or assignee.get("user_id") or "کاربر") if isinstance(assignee, dict) else "بدون مسئول"
    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(task.get("priority"), "—")
    html = (
        '<p><b>✅ بررسی نهایی تسک</b></p>'
        f"<p>📝 <b>عنوان:</b> {escape(str(task.get('title') or '—'))}</p>"
        f"<p>🎯 <b>اولویت:</b> {escape(priority)}</p>"
        f"<p>📅 <b>زمان:</b> {escape(str(task.get('deadline') or 'بدون زمان‌بندی'))}</p>"
        f"<p>📂 <b>دسته‌بندی:</b> {escape(str(task.get('category') or 'بدون دسته‌بندی'))}</p>"
        f"<p>🏷 <b>تگ:</b> {escape(str(task.get('tags') or 'بدون تگ'))}</p>"
        f"<p>👤 <b>مسئول:</b> {escape(str(name))}</p>"
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="success" data="assign_confirm_create">✅ ثبت تسک</tg-button>'
        '<tg-button type="callback_data" style="primary" data="assign_change_create">✏️ تغییر مسئول</tg-button>'
        "</tg-button-row>"
        '<tg-button-row align="center">'
        f'<tg-button type="callback_data" style="link" data="{CREATE_CANCEL_CALLBACK}">{CREATE_CANCEL_LABEL}</tg-button>'
        "</tg-button-row>"
    )
    if not await _edit_create_rich_message(context, query.message, html):
        raise RuntimeError("create-task Rich Message is not initialized")


def install_create_task_flow(task_module) -> None:
    if getattr(task_module, "_create_task_flow_guards_installed", False):
        return
    task_module._create_task_flow_guards_installed = True

    import sys
    main_module = sys.modules.get("main")

    async def shared_add_task(update, context):
        clear_create_task_state(context)
        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"
        context.user_data["create_task_user_id"] = update.effective_user.id
        await _send_create_rich_message(update.effective_message or update.callback_query.message, context.bot, context)

    task_module.add_task = shared_add_task
    if main_module is not None:
        main_module.add_task = shared_add_task

    original_skip_keyboard = task_module._skip_keyboard
    task_module._skip_keyboard = lambda callback_data: add_create_cancel(original_skip_keyboard(callback_data))
    original_category_keyboard = task_module._category_keyboard

    async def category_keyboard_with_cancel(user_id):
        return add_create_cancel(await original_category_keyboard(user_id))

    task_module._category_keyboard = category_keyboard_with_cancel
    original_priority_keyboard = task_module.priority_keyboard
    original_deadline_keyboard = task_module.deadline_keyboard
    task_module.priority_keyboard = lambda *a, **kw: add_create_cancel(original_priority_keyboard(*a, **kw))
    task_module.deadline_keyboard = lambda *a, **kw: add_create_cancel(original_deadline_keyboard(*a, **kw))

    async def ask_category_rich(message, context, user_id):
        context.user_data["step"] = "category"
        await _show_category_rich_message(task_module, message, context, user_id)

    async def ask_tags_rich(message, context):
        context.user_data["step"] = "tags"
        await _show_tags_rich_message(message, context)

    async def ask_description_rich(message, context):
        context.user_data["step"] = "description"
        await _show_description_rich_message(message, context)

    async def ask_assignment_rich(update, context):
        context.user_data["step"] = "assignment_method"
        await _show_assignment_rich_message(update.effective_message, context)

    task_module._ask_category = ask_category_rich
    task_module._ask_tags = ask_tags_rich
    task_module._ask_description = ask_description_rich
    task_module._ask_assignment = ask_assignment_rich

    try:
        import handlers.tag_suggestions_legacy as legacy
        original_recent_tag_keyboard = legacy.recent_tag_keyboard

        async def recent_tag_keyboard_with_cancel(*args, **kwargs):
            markup, tags = await original_recent_tag_keyboard(*args, **kwargs)
            return add_create_cancel(markup), tags

        legacy.recent_tag_keyboard = recent_tag_keyboard_with_cancel
    except Exception:
        pass

    original_save_task = task_module.save_task

    async def save_task_with_create_validation(update, context):
        step = context.user_data.get("step")
        if step == "title":
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
            await _edit_create_rich_message(context, update.effective_message, _priority_html())
            return
        if step == "deadline_custom":
            from utils.date_parse import parse_deadline_input
            task = context.user_data.setdefault("new_task", {})
            parsed = parse_deadline_input(str(update.effective_message.text or "").strip())
            if not parsed:
                html = '<p><b>⚠️ تاریخ نامعتبر است</b></p><p>میلادی: 2026-08-20</p><p>شمسی: 1405-05-29</p>' + _rich_rows([_rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")])
                await _edit_create_rich_message(context, update.effective_message, html)
                return
            task["deadline"] = parsed
            context.user_data["step"] = "category"
            await _show_category_rich_message(task_module, update.effective_message, context, update.effective_user.id)
            return
        return await original_save_task(update, context)

    task_module.save_task = save_task_with_create_validation
    if main_module is not None:
        main_module.save_task = save_task_with_create_validation

    async def priority_selected_rich(update, context):
        query = update.callback_query
        await query.answer()
        priority = (query.data or "").replace("priority_", "", 1)
        if priority not in _VALID_PRIORITIES:
            await query.answer("⚠️ اولویت انتخاب‌شده معتبر نیست.", show_alert=True)
            return
        context.user_data.setdefault("new_task", {})["priority"] = priority
        context.user_data["step"] = "deadline"
        await _edit_create_rich_message(context, query.message, _deadline_html())

    task_module.priority_selected = priority_selected_rich
    if main_module is not None:
        main_module.priority_selected = priority_selected_rich

    async def deadline_selected_rich(update, context):
        query = update.callback_query
        data = query.data or ""
        await query.answer()
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            await query.answer("فرایند ایجاد تسک فعالی پیدا نشد.", show_alert=True)
            return
        value = data.replace("deadline_", "", 1)
        if value == "custom":
            context.user_data["step"] = "deadline_custom"
            html = '<p><b>🕐 تاریخ و زمان دلخواه</b></p><p>تاریخ را ارسال کنید:</p><p>• میلادی: 2026-08-20</p><p>• شمسی: 1405-05-29</p>' + _rich_rows([_rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")])
            await _edit_create_rich_message(context, query.message, html)
            return
        if value == "none":
            task["deadline"] = ""
        else:
            try:
                days = int(value)
            except ValueError:
                await query.answer("تاریخ انتخاب‌شده معتبر نیست.", show_alert=True)
                return
            task["deadline"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        context.user_data["step"] = "category"
        await _show_category_rich_message(task_module, query.message, context, update.effective_user.id)

    task_module.deadline_selected = deadline_selected_rich
    if main_module is not None:
        main_module.deadline_selected = deadline_selected_rich

    original_assignment_callback = task_module.assignment_callback

    async def assignment_callback_rich(update, context):
        query = update.callback_query
        data = query.data or ""
        uid = update.effective_user.id
        if data == CREATE_CANCEL_CALLBACK:
            await query.answer()
            await _edit_create_rich_message(context, query.message, '<p><b>❌ ایجاد تسک لغو شد.</b></p>')
            clear_create_task_state(context)
            return
        if data == "assign_self" or data.startswith("assign_self_"):
            user = update.effective_user
            context.user_data.setdefault("new_task", {})["assignee"] = {"user_id": str(user.id), "display_name": user.full_name, "username": user.username or ""}
            await query.answer()
            await _show_assignment_summary_rich(query, context)
            return
        if data in ("assign_team", "assign_teams"):
            await query.answer()
            teams = await task_module.aget_user_teams(uid) if hasattr(task_module, "aget_user_teams") else []
            if not teams:
                await _edit_create_rich_message(context, query.message, '<p><b>👥 تیمی برای انتخاب مسئول پیدا نشد.</b></p>' + _rich_rows([_rich_button("🔙 بازگشت", "assign_change_create")]))
                return
            buttons = [_rich_button(f"📌 {(item.get('team') or {}).get('name') or 'تیم'}", f"assign_team_{(item.get('team') or {}).get('team_id')}") for item in teams]
            buttons += [_rich_button("🔙 بازگشت", "assign_change_create"), _rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")]
            await _edit_create_rich_message(context, query.message, '<p><b>👥 انتخاب تیم</b></p><p>تیم موردنظر را انتخاب کنید:</p>' + _rich_rows(buttons))
            return
        if data.startswith("assign_team_"):
            await query.answer()
            team_id = data.replace("assign_team_", "", 1)
            context.user_data["_create_selected_team_id"] = team_id
            members = await task_module.aget_team_members(team_id) if hasattr(task_module, "aget_team_members") else []
            buttons = [_rich_button(f"👤 {task_module.member_display(m)}", f"assign_member_{m.get('user_id')}") for m in members]
            buttons += [_rich_button("🔙 بازگشت", "assign_teams"), _rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")]
            await _edit_create_rich_message(context, query.message, '<p><b>👤 انتخاب عضو تیم</b></p>' + _rich_rows(buttons))
            return
        if data.startswith("assign_member_"):
            await query.answer()
            mid = data.replace("assign_member_", "", 1)
            team_id = context.user_data.get("_create_selected_team_id")
            members = await task_module.aget_team_members(team_id) if team_id and hasattr(task_module, "aget_team_members") else []
            member = next((m for m in members if str(m.get("user_id")) == mid), None) or {"user_id": mid, "display_name": "عضو تیم"}
            context.user_data.setdefault("new_task", {})["assignee"] = member
            await _show_assignment_summary_rich(query, context)
            return
        if data == "assign_search":
            await query.answer()
            context.user_data["step"] = "assignment_search"
            await _edit_create_rich_message(context, query.message, '<p><b>🔎 جستجوی کاربر</b></p><p>نام یا نام خانوادگی کاربر را در پیام بعدی ارسال کنید.</p>' + _rich_rows([_rich_button("🔙 بازگشت", "assign_change_create"), _rich_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link")]))
            return
        if data == "assign_none":
            await query.answer()
            context.user_data.setdefault("new_task", {})["assignee"] = None
            await _show_assignment_summary_rich(query, context)
            return
        if data == "assign_change_create":
            await query.answer()
            context.user_data["step"] = "assignment_method"
            await _show_assignment_rich_message(query.message, context)
            return
        if data == "step_back_tags":
            await query.answer()
            context.user_data["step"] = "tags"
            await _show_tags_rich_message(query.message, context)
            return
        if data == "assign_confirm_create":
            await query.answer()
            await original_assignment_callback(update, context)
            return
        return await original_assignment_callback(update, context)

    task_module.assignment_callback = assignment_callback_rich
    if main_module is not None:
        main_module.assignment_callback = assignment_callback_rich

    original_optional_callback = task_module.optional_field_callback

    async def optional_field_callback_rich(update, context):
        query = update.callback_query
        data = query.data or ""
        if data == "category_skip":
            await query.answer()
            context.user_data.setdefault("new_task", {})["category"] = ""
            await _show_tags_rich_message(query.message, context)
            return
        if data.startswith("category_pick_"):
            await query.answer()
            try:
                index = int(data.replace("category_pick_", "", 1))
            except ValueError:
                await query.answer("دسته‌بندی نامعتبر است.", show_alert=True)
                return
            categories = await task_module._category_options(update.effective_user.id)
            if 0 <= index < len(categories):
                context.user_data.setdefault("new_task", {})["category"] = categories[index]
                await _show_tags_rich_message(query.message, context)
                return
            await query.answer("دسته‌بندی انتخاب‌شده دیگر در دسترس نیست.", show_alert=True)
            return
        if data == "description_skip":
            await query.answer()
            context.user_data.setdefault("new_task", {})["description"] = ""
            await task_module._ask_assignment(update, context)
            return
        return await original_optional_callback(update, context)

    task_module.optional_field_callback = optional_field_callback_rich
    if main_module is not None:
        main_module.optional_field_callback = optional_field_callback_rich
