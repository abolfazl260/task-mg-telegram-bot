"""Rich-message runtime patch for the manual create-task flow.

The create flow deliberately uses one Telegram Rich Message. Every step edits
that message in place; legacy inline keyboards are not used for this flow.
"""

from datetime import datetime, timedelta
from html import escape
import sys

import jdatetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CREATE_CANCEL_CALLBACK = "assign_cancel_create"
CREATE_CANCEL_LABEL = "❌ لغو ایجاد تسک"
_VALID_PRIORITIES = {"high", "medium", "low"}


def _cancel_button():
    return InlineKeyboardButton(CREATE_CANCEL_LABEL, callback_data=CREATE_CANCEL_CALLBACK)


def add_create_cancel(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Keep the legacy helper available; Rich create flow does not use it."""
    rows = [list(row) for row in (markup.inline_keyboard if markup else [])]
    if not any(b.callback_data == CREATE_CANCEL_CALLBACK for row in rows for b in row):
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


def _button(text: str, data: str, style: str = "primary") -> str:
    return (
        f'<tg-button type="callback_data" style="{style}" '
        f'data="{escape(data, quote=True)}">{escape(text)}</tg-button>'
    )


def _rows(buttons, per_row=2) -> str:
    return "".join(
        '<tg-button-row align="center">' + "".join(buttons[i:i + per_row]) + "</tg-button-row>"
        for i in range(0, len(buttons), per_row)
    )


def _footer(include_back=False, back_data=None) -> str:
    buttons = []
    if include_back and back_data:
        buttons.append(_button("🔙 مرحله قبل", back_data, "link"))
    buttons.append(_button(CREATE_CANCEL_LABEL, CREATE_CANCEL_CALLBACK, "link"))
    return _rows(buttons, 2)


async def _send_rich(context, message, html):
    sent = await context.bot._post("sendRichMessage", data={
        "chat_id": message.chat_id,
        "rich_message": {"html": html, "is_rtl": True},
    })
    message_id = getattr(sent, "message_id", None)
    if not message_id:
        raise RuntimeError("Telegram did not return a Rich Message id")
    context.user_data["create_task_message_id"] = message_id
    return sent


async def _edit_rich(context, fallback_message, html):
    message_id = context.user_data.get("create_task_message_id")
    chat_id = getattr(fallback_message, "chat_id", None)
    if not message_id or not chat_id:
        return False
    await context.bot._post("editMessageText", data={
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": {"html": html, "is_rtl": True},
    })
    return True


def _priority_html():
    return (
        '<p><b>🎯 انتخاب اولویت</b></p>'
        '<p>اولویت این تسک را انتخاب کنید:</p>'
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="danger" data="priority_high">🔴 بالا</tg-button>'
        '<tg-button type="callback_data" style="primary" data="priority_medium">🟠 متوسط</tg-button>'
        '<tg-button type="callback_data" style="success" data="priority_low">🟢 پایین</tg-button>'
        '</tg-button-row>'
        + _footer()
    )


def _deadline_label(days):
    target = datetime.now().date() + timedelta(days=days)
    jalali = jdatetime.date.fromgregorian(date=target).strftime("%Y/%m/%d")
    if days == 0:
        prefix = "امروز"
    elif days == 1:
        prefix = "فردا"
    else:
        prefix = f"{days} روز بعد"
    return f"{prefix} · {jalali}"


def _deadline_html():
    dates = [_button(f"📅 {_deadline_label(i)}", f"deadline_{i}", "success" if i == 0 else "primary" if i == 1 else "primary") for i in range(8)]
    actions = [
        _button("🕐 تاریخ و زمان دلخواه", "deadline_custom", "primary"),
        _button("⏭ بدون زمان‌بندی", "deadline_none"),
    ]
    return (
        '<p><b>📅 زمان انجام</b></p>'
        '<p>زمان موردنظر را انتخاب کنید:</p>'
        + _rows(dates, 2)
        + _rows(actions, 2)
        + _footer(True, "step_back_priority")
    )


async def _show_category(task_module, message, context, user_id):
    categories = await task_module._category_options(user_id)
    buttons = [_button(f"📂 {str(category)[:32]}", f"category_pick_{i}") for i, category in enumerate(categories)]
    if buttons:
        html = '<p><b>📂 دسته‌بندی</b></p><p>دسته‌بندی تسک را انتخاب کنید:</p>' + _rows(buttons, 2)
    else:
        html = '<p><b>📂 دسته‌بندی</b></p><p>دسته‌بندی‌ای برای انتخاب وجود ندارد.</p>'
    html += _rows([_button("⏭ بدون دسته‌بندی", "category_skip")]) + _footer()
    context.user_data["step"] = "category"
    await _edit_rich(context, message, html)


async def _show_tags(message, context):
    from handlers import tag_suggestions_legacy as legacy
    user_id = context.user_data.get("create_task_user_id") or getattr(getattr(message, "from_user", None), "id", 0)
    _, tags = await legacy.recent_tag_keyboard(user_id, limit=3)
    context.user_data["tag_suggestions"] = tags
    buttons = [_button(f"🏷 {str(tag)[:32]}", f"tag_pick_{i}") for i, tag in enumerate(tags)]
    html = '<p><b>🏷 تگ‌ها</b></p><p>تگ پیشنهادی را انتخاب کنید:</p>'
    if buttons:
        html += _rows(buttons, 2)
    html += _rows([_button("➕ تگ جدید", "tag_new", "success"), _button("⏭ بدون تگ", "tags_skip")], 2)
    html += _footer(True, "step_back_category")
    context.user_data["step"] = "tags"
    await _edit_rich(context, message, html)


async def _show_description(message, context):
    context.user_data["step"] = "description"
    html = (
        '<p><b>📄 توضیحات تسک</b></p>'
        '<p>توضیح یا یادداشت را در پیام بعدی ارسال کنید.</p>'
        '<p><i>این بخش اختیاری است.</i></p>'
        + _rows([_button("⏭ بدون توضیحات", "description_skip")])
        + _footer(True, "step_back_tags")
    )
    await _edit_rich(context, message, html)


async def _show_assignment(message, context):
    context.user_data["step"] = "assignment_method"
    html = (
        '<p><b>👤 انتخاب مسئول</b></p><p>این تسک به چه کسی اختصاص داده شود؟</p>'
        + _rows([
            _button("🙋‍♂️ خودم", "assign_self", "success"),
            _button("👥 هم‌تیمی‌ها", "assign_teams", "primary"),
            _button("🔎 جستجوی کاربر", "assign_search", "primary"),
            _button("⏭ بدون مسئول", "assign_none"),
        ], 2)
        + _footer(True, "step_back_description")
    )
    await _edit_rich(context, message, html)


async def _show_summary(query, context):
    task = context.user_data.setdefault("new_task", {})
    assignee = task.get("assignee")
    if isinstance(assignee, dict):
        name = assignee.get("display_name") or assignee.get("username") or str(assignee.get("user_id") or "کاربر")
    else:
        name = "بدون مسئول"
    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(task.get("priority"), "—")
    html = (
        '<p><b>✅ بررسی نهایی تسک</b></p>'
        f'<p>📝 <b>عنوان:</b> {escape(str(task.get("title") or "—"))}</p>'
        f'<p>🎯 <b>اولویت:</b> {escape(priority)}</p>'
        f'<p>📅 <b>زمان:</b> {escape(str(task.get("deadline") or "بدون زمان‌بندی"))}</p>'
        f'<p>📂 <b>دسته‌بندی:</b> {escape(str(task.get("category") or "بدون دسته‌بندی"))}</p>'
        f'<p>🏷 <b>تگ:</b> {escape(str(task.get("tags") or "بدون تگ"))}</p>'
        f'<p>👤 <b>مسئول:</b> {escape(str(name))}</p>'
        + _rows([
            _button("✅ ثبت تسک", "assign_confirm_create", "success"),
            _button("✏️ تغییر مسئول", "assign_change_create", "primary"),
        ], 2)
        + _footer()
    )
    await _edit_rich(context, query.message, html)


def install_create_task_flow(task_module):
    if getattr(task_module, "_create_task_flow_guards_installed", False):
        return
    task_module._create_task_flow_guards_installed = True
    main_module = sys.modules.get("main")

    # Keep the original functions for non-create-task flows.
    original_save_task = task_module.save_task
    original_assignment = task_module.assignment_callback
    original_optional = task_module.optional_field_callback

    async def add_task_rich(update, context):
        clear_create_task_state(context)
        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"
        context.user_data["create_task_user_id"] = update.effective_user.id
        message = update.effective_message or update.callback_query.message
        html = (
            '<p><b>📝 ایجاد تسک جدید</b></p>'
            '<p>عنوان تسک را در پیام بعدی ارسال کنید.</p>'
            + _footer()
        )
        await _send_rich(context, message, html)

    task_module.add_task = add_task_rich
    if main_module:
        main_module.add_task = add_task_rich

    async def ask_category(message, context, user_id):
        await _show_category(task_module, message, context, user_id)

    async def ask_tags(message, context):
        await _show_tags(message, context)

    async def ask_description(message, context):
        await _show_description(message, context)

    async def ask_assignment(update, context):
        await _show_assignment(update.effective_message, context)

    task_module._ask_category = ask_category
    task_module._ask_tags = ask_tags
    task_module._ask_description = ask_description
    task_module._ask_assignment = ask_assignment

    async def save_task_rich(update, context):
        step = context.user_data.get("step")
        message = update.effective_message
        if not message:
            return await original_save_task(update, context)

        if step == "title":
            title = str(message.text or "").strip()
            if not title:
                await _edit_rich(context, message, '<p><b>⚠️ عنوان خالی است.</b></p><p>لطفاً عنوان تسک را ارسال کنید.</p>' + _footer())
                return
            if len(title) > 200:
                await _edit_rich(context, message, '<p><b>⚠️ عنوان بیش از حد طولانی است.</b></p><p>حداکثر ۲۰۰ کاراکتر مجاز است.</p>' + _footer())
                return
            context.user_data.setdefault("new_task", {})["title"] = title
            context.user_data["step"] = "priority"
            await _edit_rich(context, message, _priority_html())
            return

        if step == "deadline_custom":
            from utils.date_parse import parse_deadline_input
            parsed = parse_deadline_input(str(message.text or "").strip())
            if not parsed:
                html = '<p><b>⚠️ تاریخ نامعتبر است.</b></p><p>فرمت تاریخ را دوباره ارسال کنید.</p><p>مثال: <code>1405-06-15</code> یا <code>2026-09-06</code></p>' + _footer()
                await _edit_rich(context, message, html)
                return
            context.user_data.setdefault("new_task", {})["deadline"] = parsed
            await _show_category(task_module, message, context, update.effective_user.id)
            return

        # Tags and description text are intentionally routed through their
        # existing state machine; their next prompt is patched to edit Rich.
        return await original_save_task(update, context)

    task_module.save_task = save_task_rich
    if main_module:
        main_module.save_task = save_task_rich

    async def priority_rich(update, context):
        query = update.callback_query
        await query.answer()
        value = (query.data or "").replace("priority_", "", 1)
        if value not in _VALID_PRIORITIES:
            await query.answer("اولویت نامعتبر است.", show_alert=True)
            return
        context.user_data.setdefault("new_task", {})["priority"] = value
        context.user_data["step"] = "deadline"
        await _edit_rich(context, query.message, _deadline_html())

    async def deadline_rich(update, context):
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            await query.answer("فرایند ایجاد تسک فعال نیست.", show_alert=True)
            return
        value = data.replace("deadline_", "", 1)
        if value == "custom":
            context.user_data["step"] = "deadline_custom"
            await _edit_rich(context, query.message, '<p><b>🕐 تاریخ دلخواه</b></p><p>تاریخ و زمان را در پیام بعدی ارسال کنید.</p><p>مثال: <code>1405-06-15</code> یا <code>2026-09-06</code></p>' + _footer())
            return
        if value == "none":
            task["deadline"] = ""
        else:
            try:
                days = int(value)
                task["deadline"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            except ValueError:
                await query.answer("تاریخ نامعتبر است.", show_alert=True)
                return
        await _show_category(task_module, query.message, context, update.effective_user.id)

    task_module.priority_selected = priority_rich
    task_module.deadline_selected = deadline_rich
    if main_module:
        main_module.priority_selected = priority_rich
        main_module.deadline_selected = deadline_rich

    async def optional_rich(update, context):
        query = update.callback_query
        data = query.data or ""
        if data == "category_skip":
            await query.answer()
            context.user_data.setdefault("new_task", {})["category"] = ""
            await _show_tags(query.message, context)
            return
        if data.startswith("category_pick_"):
            await query.answer()
            try:
                index = int(data.rsplit("_", 1)[1])
                categories = await task_module._category_options(update.effective_user.id)
                if not 0 <= index < len(categories):
                    raise ValueError
            except (ValueError, TypeError):
                await query.answer("دسته‌بندی نامعتبر است.", show_alert=True)
                return
            context.user_data.setdefault("new_task", {})["category"] = categories[index]
            await _show_tags(query.message, context)
            return
        if data == "description_skip":
            await query.answer()
            context.user_data.setdefault("new_task", {})["description"] = ""
            await _show_assignment(query.message, context)
            return
        return await original_optional(update, context)

    task_module.optional_field_callback = optional_rich
    if main_module:
        main_module.optional_field_callback = optional_rich

    async def tag_callback_rich(update, context):
        query = update.callback_query
        data = query.data or ""
        if not (data.startswith("tag_") or data.startswith("tags_") or data in {"step_back_category", "step_back_description"}):
            return
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            await query.answer("فرایند ایجاد تسک فعال نیست.", show_alert=True)
            return
        await query.answer()
        if data in {"tags_skip", "tag_none"}:
            task["tags"] = ""
            context.user_data.pop("tag_suggestions", None)
            context.user_data.pop("awaiting_tag_input", None)
            await _show_description(query.message, context)
            return
        if data in {"tag_new", "tags_new"}:
            context.user_data["step"] = "tags"
            context.user_data["awaiting_tag_input"] = True
            await _edit_rich(context, query.message, '<p><b>➕ تگ جدید</b></p><p>نام تگ را در پیام بعدی ارسال کنید.</p>' + _footer(True, "step_back_category"))
            return
        if data == "step_back_category":
            await _show_category(task_module, query.message, context, update.effective_user.id)
            return
        if data == "step_back_description":
            await _show_description(query.message, context)
            return
        if data.startswith("tag_pick_"):
            try:
                index = int(data.rsplit("_", 1)[1])
                tags = context.user_data.get("tag_suggestions") or []
                if not 0 <= index < len(tags):
                    raise ValueError
            except (ValueError, TypeError):
                await query.answer("تگ نامعتبر است.", show_alert=True)
                return
            task["tags"] = tags[index]
            context.user_data.pop("tag_suggestions", None)
            context.user_data.pop("awaiting_tag_input", None)
            await _show_description(query.message, context)

    task_module._handle_tag_callback = tag_callback_rich

    async def tag_text_rich(update, context):
        if context.user_data.get("step") != "tags":
            return False
        text = str(getattr(update.effective_message, "text", "") or "").strip()
        if not text:
            return False
        context.user_data.setdefault("new_task", {})["tags"] = text[:120]
        context.user_data.pop("tag_suggestions", None)
        context.user_data.pop("awaiting_tag_input", None)
        await _show_description(update.effective_message, context)
        return True

    task_module._handle_tag_text = tag_text_rich

    async def assignment_rich(update, context):
        query = update.callback_query
        data = query.data or ""
        if not data.startswith("assign_") and data not in {"step_back_tags", CREATE_CANCEL_CALLBACK}:
            return await original_assignment(update, context)
        await query.answer()
        if data == CREATE_CANCEL_CALLBACK:
            await _edit_rich(context, query.message, '<p><b>❌ ایجاد تسک لغو شد.</b></p>')
            clear_create_task_state(context)
            return
        if data == "assign_self":
            user = update.effective_user
            context.user_data.setdefault("new_task", {})["assignee"] = {"user_id": str(user.id), "display_name": user.full_name, "username": user.username or ""}
            await _show_summary(query, context)
            return
        if data == "assign_none":
            context.user_data.setdefault("new_task", {})["assignee"] = None
            await _show_summary(query, context)
            return
        if data == "assign_change_create":
            await _show_assignment(query.message, context)
            return
        if data == "step_back_tags":
            await _show_tags(query.message, context)
            return
        if data == "assign_teams":
            teams = await task_module.aget_user_teams(update.effective_user.id) if hasattr(task_module, "aget_user_teams") else []
            buttons = [_button(f"📌 {(x.get('team') or {}).get('name') or 'تیم'}", f"assign_team_{(x.get('team') or {}).get('team_id')}") for x in teams]
            html = '<p><b>👥 انتخاب تیم</b></p><p>تیم موردنظر را انتخاب کنید:</p>' + (_rows(buttons, 2) if buttons else '<p>تیمی پیدا نشد.</p>') + _footer(True, "assign_change_create")
            await _edit_rich(context, query.message, html)
            return
        if data.startswith("assign_team_"):
            team_id = data.replace("assign_team_", "", 1)
            context.user_data["_create_selected_team_id"] = team_id
            members = await task_module.aget_team_members(team_id) if hasattr(task_module, "aget_team_members") else []
            buttons = [_button(f"👤 {task_module.member_display(m)}", f"assign_member_{m.get('user_id')}") for m in members]
            await _edit_rich(context, query.message, '<p><b>👤 انتخاب عضو</b></p>' + (_rows(buttons, 2) if buttons else '<p>عضوی پیدا نشد.</p>') + _footer(True, "assign_teams"))
            return
        if data.startswith("assign_member_"):
            member_id = data.replace("assign_member_", "", 1)
            team_id = context.user_data.get("_create_selected_team_id")
            members = await task_module.aget_team_members(team_id) if team_id and hasattr(task_module, "aget_team_members") else []
            member = next((m for m in members if str(m.get("user_id")) == member_id), {"user_id": member_id, "display_name": "عضو تیم"})
            context.user_data.setdefault("new_task", {})["assignee"] = member
            await _show_summary(query, context)
            return
        if data == "assign_search":
            context.user_data["step"] = "assignment_search"
            await _edit_rich(context, query.message, '<p><b>🔎 جستجوی کاربر</b></p><p>نام یا نام خانوادگی را در پیام بعدی ارسال کنید.</p>' + _footer(True, "assign_change_create"))
            return
        if data == "assign_confirm_create":
            # Preserve the existing finalization/database logic.
            await original_assignment(update, context)
            return
        return await original_assignment(update, context)

    task_module.assignment_callback = assignment_rich
    if main_module:
        main_module.assignment_callback = assignment_rich

    # Make the tag module use the same Rich callback/text handlers instead of
    # its legacy inline-keyboard callbacks for create-task updates.
    try:
        import handlers.tag_suggestions_legacy as legacy
        legacy._handle_tag_callback = tag_callback_rich
        legacy._handle_tag_text = tag_text_rich
    except Exception:
        pass
