from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import get_all_user_tasks, get_task_by_id
from services.team_service import get_user_teams, get_team_members, member_display


def _split_tags(raw):
    if not raw:
        return []
    return [
        item.strip().lstrip("#")
        for item in str(raw).replace("\n", ",").replace("،", ",").split(",")
        if item.strip()
    ]


def get_suggested_tags(user_id, limit=12):
    seen = set()
    result = []
    for task in get_all_user_tasks(user_id):
        for tag in _split_tags(task.get("tags")):
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                result.append(tag)
            if len(result) >= limit:
                return result
    return result


def _tag_keyboard(tags, context):
    context.user_data["tag_suggestions"] = list(tags)
    rows = [[InlineKeyboardButton(f"🏷 {tag}", callback_data=f"tags_pick_{index}")] for index, tag in enumerate(tags)]
    rows.append([InlineKeyboardButton("➕ تگ جدید", callback_data="tags_new")])
    rows.append([InlineKeyboardButton("⏭ بدون تگ", callback_data="tags_skip")])
    return InlineKeyboardMarkup(rows)


def _ui_message(context, message):
    if message is not None:
        context.user_data["task_ui_message_id"] = message.message_id
        context.user_data["task_ui_chat_id"] = message.chat_id
    return message


async def _edit_task_ui(message, context, text, reply_markup=None, parse_mode=None):
    _ui_message(context, message)
    kwargs = {"text": text, "reply_markup": reply_markup}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    try:
        await message.edit_text(**kwargs)
    except Exception:
        sent = await message.reply_text(**kwargs)
        _ui_message(context, sent)


def _task_ui_text(task, step):
    title = task.get("title") or "—"
    priority = task.get("priority")
    priority_label = {"high": "🔴 بالا", "medium": "🟡 متوسط", "low": "🟢 پایین"}.get(priority, "—")
    deadline = task.get("deadline") or ""
    deadline_label = deadline or "—"
    if deadline:
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
            diff = (d - datetime.now().date()).days
            if diff == 0:
                deadline_label = "امروز"
            elif diff == 1:
                deadline_label = "فردا"
        except Exception:
            pass

    lines = ["📋 **افزودن تسک**", "", f"**عنوان:** {title}"]
    if priority:
        lines.append(f"**اولویت:** {priority_label}")
    if deadline:
        lines.append(f"**مهلت:** {deadline_label}")

    prompts = {
        "title": "عنوان تسک را وارد کنید:",
        "priority": "حالا اولویت را انتخاب کنید:",
        "deadline": "مهلت را انتخاب کنید:",
        "deadline_custom": "تاریخ دقیق را وارد کنید:\nمثال: 2026-08-20 یا 1405-05-29",
        "category": "دسته‌بندی را انتخاب کنید یا نام دسته‌بندی جدید را وارد کنید:",
        "tags": "تگ را انتخاب کنید یا تگ جدید وارد کنید:",
        "description": "توضیح / یادداشت را وارد کنید یا رد کنید:",
        "assignment_method": "مسئول تسک را انتخاب کنید:",
        "assignment_search": "نام یا نام خانوادگی کاربر را وارد کنید:",
    }
    if step in prompts:
        lines += ["", prompts[step]]
    return "\n".join(lines)


def install_tag_flow(task_module):
    """Install reusable tag suggestions and the single-message task creation flow."""
    original_save_task = task_module.save_task
    original_assignment_callback = task_module.assignment_callback

    async def _ask_tags(message, context):
        context.user_data["step"] = "tags"
        user_id = getattr(getattr(message, "chat", None), "id", 0)
        tags = get_suggested_tags(user_id)
        await _edit_task_ui(message, context, _task_ui_text(context.user_data.get("new_task", {}), "tags"), _tag_keyboard(tags, context))

    async def _ask_description(message, context):
        context.user_data["step"] = "description"
        await _edit_task_ui(message, context, _task_ui_text(context.user_data.get("new_task", {}), "description"), InlineKeyboardMarkup([[InlineKeyboardButton("⏭ رد کردن", callback_data="description_skip")]]))

    async def _ask_category(message, context, user_id):
        context.user_data["step"] = "category"
        await _edit_task_ui(message, context, _task_ui_text(context.user_data.get("new_task", {}), "category"), task_module._category_keyboard(user_id))

    async def _ask_assignment(update, context):
        context.user_data["step"] = "assignment_method"
        await _edit_task_ui(
            update.effective_message, context, _task_ui_text(context.user_data.get("new_task", {}), "assignment_method"),
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="assign_search")],
                [InlineKeyboardButton("👥 انتخاب از اعضای تیم", callback_data="assign_teams")],
                [InlineKeyboardButton("⏭ بدون مسئول", callback_data="assign_none")],
            ])
        )

    async def add_task_single(update, context):
        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"
        context.user_data.pop("task_ui_message_id", None)
        context.user_data.pop("task_ui_chat_id", None)
        await _edit_task_ui(update.effective_message, context, _task_ui_text({}, "title"), None)

    async def save_task_single(update, context):
        step = context.user_data.get("step")
        task = context.user_data.get("new_task")
        message = update.effective_message

        if isinstance(task, dict) and step == "title" and message and message.text:
            task["title"] = message.text.strip()
            if not task["title"]:
                return
            context.user_data["step"] = "priority"
            await _edit_task_ui(message, context, _task_ui_text(task, "priority"), task_module.priority_keyboard())
            return

        if isinstance(task, dict) and step == "deadline_custom" and message and message.text:
            parsed = task_module.parse_deadline_input(message.text.strip())
            if not parsed:
                await _edit_task_ui(message, context, _task_ui_text(task, "deadline_custom") + "\n\n⚠️ تاریخ واردشده معتبر نیست.", None)
                return
            task["deadline"] = parsed
            await _ask_category(message, context, update.effective_user.id)
            return

        if isinstance(task, dict) and step == "category" and message and message.text:
            task["category"] = message.text.strip()
            await _ask_tags(message, context)
            return

        if isinstance(task, dict) and step == "tags" and message and message.text:
            task["tags"] = message.text.strip()[:120]
            await _ask_description(message, context)
            return

        if isinstance(task, dict) and step == "description" and message and message.text:
            task["description"] = message.text.strip()
            await _ask_assignment(update, context)
            return

        if isinstance(task, dict) and step == "assignment_search" and message and message.text:
            q = message.text.strip().lower()
            matches = []
            for team in get_user_teams(update.effective_user.id):
                for member in get_team_members(team["team"]["team_id"]):
                    blob = f"{member.get('display_name','')} {member.get('username','')}".lower()
                    if q and q in blob:
                        matches.append(member)
            if not matches:
                await _edit_task_ui(message, context, _task_ui_text(task, "assignment_search") + "\n\n❌ نتیجه‌ای پیدا نشد.", None)
                return
            rows = [[InlineKeyboardButton(f"انتخاب: {member_display(m)}", callback_data=f"assign_member_{m.get('user_id')}")] for m in matches[:10]]
            context.user_data["step"] = "assignment_method"
            await _edit_task_ui(message, context, _task_ui_text(task, "assignment_method") + "\n\nنتایج جستجو:", InlineKeyboardMarkup(rows))
            return

        await original_save_task(update, context)

    async def priority_single(update, context):
        query = update.callback_query
        await query.answer()
        priority = (query.data or "").replace("priority_", "")
        if priority not in ("high", "medium", "low"):
            return
        task = context.user_data.setdefault("new_task", {})
        task["priority"] = priority
        context.user_data["step"] = "deadline"
        await _edit_task_ui(query.message, context, _task_ui_text(task, "deadline"), task_module.deadline_keyboard())

    async def deadline_single(update, context):
        query = update.callback_query
        await query.answer()
        value = (query.data or "").replace("deadline_", "")
        task = context.user_data.setdefault("new_task", {})
        if value == "custom":
            context.user_data["step"] = "deadline_custom"
            await _edit_task_ui(query.message, context, _task_ui_text(task, "deadline_custom"), None)
            return
        if value == "none":
            task["deadline"] = ""
        else:
            try:
                days = int(value)
            except ValueError:
                days = 0
            task["deadline"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        await _ask_category(query.message, context, update.effective_user.id)

    async def optional_single(update, context):
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            return
        if data == "category_skip":
            task["category"] = ""
            await _ask_tags(query.message, context)
            return
        if data.startswith("category_pick_"):
            task["category"] = data.replace("category_pick_", "", 1)
            await _ask_tags(query.message, context)
            return
        if data == "description_skip":
            task["description"] = ""
            await _ask_assignment(update, context)
            return
        await task_module.optional_field_callback(update, context)

    async def assignment_single(update, context):
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            return
        uid = update.effective_user.id

        if data == "assign_search":
            context.user_data["step"] = "assignment_search"
            await _edit_task_ui(query.message, context, _task_ui_text(task, "assignment_search"), None)
            return
        if data == "assign_teams":
            teams = get_user_teams(uid)
            if not teams:
                await _edit_task_ui(query.message, context, _task_ui_text(task, "assignment_method") + "\n\n❌ تیم مشترکی ندارید.", None)
                return
            rows = [[InlineKeyboardButton(f"📌 {i['team']['name']}", callback_data=f"assign_team_{i['team']['team_id']}")] for i in teams]
            await _edit_task_ui(query.message, context, _task_ui_text(task, "assignment_method") + "\n\nانتخاب تیم:", InlineKeyboardMarkup(rows))
            return
        if data.startswith("assign_team_"):
            team_id = data.replace("assign_team_", "", 1)
            members = get_team_members(team_id)
            rows = [[InlineKeyboardButton(f"🖼 {member_display(m)}", callback_data=f"assign_member_{m.get('user_id')}")] for m in members]
            await _edit_task_ui(query.message, context, _task_ui_text(task, "assignment_method") + "\n\nاعضای تیم:", InlineKeyboardMarkup(rows))
            return
        if data.startswith("assign_member_"):
            mid = data.replace("assign_member_", "", 1)
            member = None
            for team in get_user_teams(uid):
                for candidate in get_team_members(team["team"]["team_id"]):
                    if str(candidate.get("user_id")) == str(mid):
                        member = candidate
                        break
                if member:
                    break
            if not member:
                return
            task["assignee"] = member
            await _edit_task_ui(query.message, context, task_module._assignment_summary(task), task_module._confirm_create_keyboard())
            return
        if data == "assign_none":
            task["assignee"] = None
            await _edit_task_ui(query.message, context, task_module._assignment_summary(task), task_module._confirm_create_keyboard())
            return
        if data == "assign_change_create":
            await _ask_assignment(update, context)
            return
        if data == "assign_cancel_create":
            context.user_data.clear()
            await _edit_task_ui(query.message, context, "❌ ایجاد تسک لغو شد.", None)
            return
        if data == "assign_confirm_create":
            task_id = task_module._finalize_task(uid, task)
            saved = get_task_by_id(task_id)
            assignee = task.get("assignee")
            title = task.get("title", "-")
            priority = {"high": "🔴 بالا", "medium": "🟡 متوسط", "low": "🟢 پایین"}.get(task.get("priority"), "—")
            deadline = task.get("deadline") or "بدون مهلت"
            context.user_data.clear()
            await _edit_task_ui(query.message, context, f"✅ **تسک با موفقیت ایجاد شد**\n\n📌 {title}\n{priority}\n📅 مهلت: {deadline}", None)
            if assignee:
                await task_module._notify_assignment(context, saved or task, assignee, update.effective_user)
            return

        await original_assignment_callback(update, context)

    task_module._ask_tags = _ask_tags
    task_module._ask_description = _ask_description
    task_module._ask_category = _ask_category
    task_module._ask_assignment = _ask_assignment
    task_module.add_task = add_task_single
    task_module.save_task = save_task_single
    task_module.priority_selected = priority_single
    task_module.deadline_selected = deadline_single
    task_module.optional_field_callback = optional_single
    task_module.assignment_callback = assignment_single


async def handle_tag_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("tags_"):
        return
    await query.answer()
    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        return
    import handlers.task as task_module
    if data == "tags_skip":
        task["tags"] = ""
        context.user_data.pop("tag_suggestions", None)
        await task_module._ask_description(query.message, context)
        return
    if data == "tags_new":
        context.user_data["step"] = "tags"
        await _edit_task_ui(query.message, context, _task_ui_text(task, "tags") + "\n\nتگ جدید را وارد کنید:", None)
        return
    if data.startswith("tags_pick_"):
        try:
            index = int(data.replace("tags_pick_", "", 1))
        except ValueError:
            return
        suggestions = context.user_data.get("tag_suggestions") or []
        if 0 <= index < len(suggestions):
            task["tags"] = suggestions[index]
            context.user_data.pop("tag_suggestions", None)
            await task_module._ask_description(query.message, context)


async def handle_tag_text(update, context):
    if context.user_data.get("step") != "tags":
        from handlers.task import save_task
        await save_task(update, context)
        return True

    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        return False
    message = update.effective_message
    text = (message.text or "").strip()
    if not text:
        return False
    if text in ("بدون تگ", "بدون", "ندارم", "هیچ"):
        task["tags"] = ""
    else:
        task["tags"] = text[:120]
    context.user_data.pop("tag_suggestions", None)
    from handlers.task import _ask_description
    await _ask_description(message, context)
    return True


async def safe_assignment_confirm(update, context):
    query = update.callback_query
    if (query.data or "") != "assign_confirm_create":
        return

    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        await query.answer("فرایند ایجاد تسک منقضی شده است.", show_alert=True)
        await query.message.edit_text("⚠️ اطلاعات تسک ناقص است. لطفاً تسک را دوباره از ابتدا ایجاد کنید.")
        context.user_data.clear()
        return

    missing = []
    if not (task.get("title") or "").strip():
        missing.append("عنوان")
    if task.get("priority") not in ("high", "medium", "low"):
        missing.append("اولویت")

    if missing:
        await query.answer("اطلاعات تسک ناقص است.", show_alert=True)
        await query.message.edit_text("⚠️ امکان ثبت این تسک وجود ندارد چون اطلاعات زیر ناقص است:\n" + "، ".join(missing) + "\n\nلطفاً تسک را دوباره از ابتدا ایجاد کنید.")
        context.user_data.clear()
        return

    from handlers.task import assignment_callback
    await assignment_callback(update, context)
