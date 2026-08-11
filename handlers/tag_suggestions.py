import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from services.team_service import get_user_teams, get_team_members, member_display
from utils.keyboard import recent_tag_keyboard, assignment_grid_keyboard


def _split_tags(raw):
    if not raw:
        return []
    return [
        item.strip().lstrip("#")
        for item in str(raw).replace("\n", ",").replace("،", ",").split(",")
        if item.strip()
    ]


def _visible_members(user_id):
    members = {}
    for item in get_user_teams(user_id):
        team_id = (item.get("team") or {}).get("team_id")
        if not team_id:
            continue
        for member in get_team_members(team_id):
            uid = str(member.get("user_id") or "")
            if uid:
                members[uid] = member
    return list(members.values())


def _top_assignees(user_id, limit=3):
    members = _visible_members(user_id)
    return [(member, 0) for member in members[:limit]]


async def handle_tag_text(update, context):
    """Public dispatcher kept for main.py startup compatibility."""
    from handlers import task as task_module
    callback = getattr(task_module, "_handle_tag_text", None)
    if callback is None:
        return False
    return await callback(update, context)


async def _safe_edit(query, text, reply_markup=None):
    """Edit a callback message without crashing on Telegram's no-op error."""
    try:
        return await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return None
        raise


def install_tag_flow(task_module):
    """Install the async tag and compact assignment flow used by task creation."""
    if getattr(task_module, "_smart_tag_flow_installed", False):
        return
    task_module._smart_tag_flow_installed = True
    original_assignment_callback = task_module.assignment_callback
    original_save_task = task_module.save_task

    async def ask_tags(message, context):
        context.user_data["step"] = "tags"
        user = getattr(message, "from_user", None)
        user_id = getattr(user, "id", 0)
        keyboard, tags = await recent_tag_keyboard(user_id)
        context.user_data["tag_suggestions"] = tags
        await message.reply_text(
            "🏷 تگ را انتخاب کنید یا تگ جدید را وارد کنید:",
            reply_markup=keyboard,
        )

    async def ask_assignment(update, context):
        context.user_data["step"] = "assignment_method"
        await update.effective_message.reply_text(
            "👤 انتخاب مسئول وظیفه",
            reply_markup=assignment_grid_keyboard(),
        )

    async def _show_assignment_summary(query, context):
        task = context.user_data.setdefault("new_task", {})
        await _safe_edit(
            query,
            task_module._assignment_summary(task),
            reply_markup=task_module._confirm_create_keyboard(),
        )

    async def _show_team_picker(query, user_id):
        teams = await task_module.aget_user_teams(user_id) if hasattr(task_module, "aget_user_teams") else []
        if not teams:
            teams = await _aget_user_teams(user_id)
        if not teams:
            await _safe_edit(
                query,
                "تیم مشترکی برای انتخاب مسئول ندارید.",
                reply_markup=assignment_grid_keyboard(),
            )
            return
        keyboard = [
            [InlineKeyboardButton(f"📌 {item['team']['name']}", callback_data=f"assign_team_{item['team']['team_id']}")]
            for item in teams
        ]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="step_back_tags")])
        await _safe_edit(
            query,
            "👥 هم‌تیمی‌ها را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def assignment_callback(update, context):
        query = update.callback_query
        data = query.data or ""
        uid = update.effective_user.id
        await query.answer()

        if data == "assign_self":
            user = update.effective_user
            task = context.user_data.setdefault("new_task", {})
            task["assignee"] = {
                "user_id": str(user.id),
                "display_name": user.full_name,
                "username": user.username or "",
            }
            await _show_assignment_summary(query, context)
            return

        if data == "assign_team":
            await _show_team_picker(query, uid)
            return

        if data == "assign_search":
            context.user_data["step"] = "assignment_search"
            await _safe_edit(
                query,
                "🔎 نام یا نام خانوادگی کاربر را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="step_back_tags")]]),
            )
            return

        if data == "assign_none":
            context.user_data.setdefault("new_task", {})["assignee"] = None
            await _show_assignment_summary(query, context)
            return

        if data == "step_back_tags":
            keyboard, tags = await recent_tag_keyboard(uid)
            context.user_data["step"] = "tags"
            context.user_data["tag_suggestions"] = tags
            await _safe_edit(
                query,
                "🏷 تگ را انتخاب کنید یا تگ جدید را وارد کنید:",
                reply_markup=keyboard,
            )
            return

        if data.startswith("assign_team_"):
            team_id = data.replace("assign_team_", "", 1)
            members = await _aget_team_members(team_id)
            if not members:
                await _safe_edit(
                    query,
                    "اعضای قابل انتخابی در این تیم پیدا نشد.",
                    reply_markup=assignment_grid_keyboard(),
                )
                return
            keyboard = [
                [InlineKeyboardButton(f"🖼 {member_display(member)}", callback_data=f"assign_member_{member.get('user_id')}")]
                for member in members
            ]
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="assign_team")])
            await _safe_edit(
                query,
                "👥 عضو تیم را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        if data.startswith("assign_member_"):
            mid = data.replace("assign_member_", "", 1)
            member = next((m for m in await _aget_visible_assignment_members(uid) if str(m.get("user_id")) == mid), None)
            if not member:
                await _safe_edit(
                    query,
                    "کاربر انتخاب‌شده در تیم مشترک پیدا نشد.",
                    reply_markup=assignment_grid_keyboard(),
                )
                return
            context.user_data.setdefault("new_task", {})["assignee"] = member
            await _show_assignment_summary(query, context)
            return

        if data == "assign_change_create":
            context.user_data["step"] = "assignment_method"
            await _safe_edit(query, "👤 انتخاب مسئول وظیفه", reply_markup=assignment_grid_keyboard())
            return

        if data == "assign_cancel_create":
            context.user_data.clear()
            await _safe_edit(query, "❌ ایجاد تسک لغو شد.")
            return

        return await original_assignment_callback(update, context)

    async def handle_tag_callback(update, context):
        query = update.callback_query
        data = query.data or ""
        if not (data.startswith("tag_") or data.startswith("tags_")) and data != "step_back_description":
            return
        await query.answer()
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            return

        description_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ رد کردن", callback_data="description_skip")]
        ])

        if data in ("tag_none", "tags_skip"):
            task["tags"] = ""
            context.user_data.pop("tag_suggestions", None)
            context.user_data["step"] = "description"
            await _safe_edit(
                query,
                "📄 توضیح / یادداشت را وارد کنید یا دکمه «رد کردن» را بزنید:\n(اختیاری)",
                reply_markup=description_keyboard,
            )
            return

        if data in ("tag_new", "tags_new"):
            context.user_data["step"] = "tags"
            await _safe_edit(
                query,
                "🏷 تگ جدید را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏭ بدون تگ (رد شدن)", callback_data="tag_none")],
                    [InlineKeyboardButton("🔙 مرحله قبل", callback_data="step_back_description")],
                ]),
            )
            return

        if data == "step_back_description":
            context.user_data["step"] = "description"
            await _safe_edit(
                query,
                "📄 توضیح / یادداشت را وارد کنید یا دکمه «رد کردن» را بزنید:\n(اختیاری)",
                reply_markup=description_keyboard,
            )
            return

        if data.startswith("tag_pick_"):
            try:
                index = int(data.replace("tag_pick_", "", 1))
            except ValueError:
                return
            tags = context.user_data.get("tag_suggestions") or []
            if 0 <= index < len(tags):
                task["tags"] = tags[index]
                context.user_data.pop("tag_suggestions", None)
                context.user_data["step"] = "description"
                await _safe_edit(
                    query,
                    "📄 توضیح / یادداشت را وارد کنید یا دکمه «رد کردن» را بزنید:\n(اختیاری)",
                    reply_markup=description_keyboard,
                )

    async def _handle_tag_text(update, context):
        if context.user_data.get("step") != "tags":
            return False
        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            return False
        text = (update.effective_message.text or "").strip()
        if not text:
            return False
        task["tags"] = "" if text in ("بدون تگ", "بدون", "ندارم", "هیچ") else text[:120]
        context.user_data.pop("tag_suggestions", None)
        from handlers.task import _ask_description
        await _ask_description(update.effective_message, context)
        return True

    async def save_task_with_tag_text(update, context):
        if await _handle_tag_text(update, context):
            return
        return await original_save_task(update, context)

    task_module._ask_tags = ask_tags
    task_module._ask_assignment = ask_assignment
    task_module.assignment_callback = assignment_callback
    task_module._handle_tag_callback = handle_tag_callback
    task_module._handle_tag_text = _handle_tag_text
    task_module.save_task = save_task_with_tag_text

    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.assignment_callback = assignment_callback
        main_module.handle_tag_callback = handle_tag_callback
        main_module.handle_tag_text = _handle_tag_text
        main_module.save_task = save_task_with_tag_text


async def _aget_user_teams(user_id):
    return await __import__("services.team_service", fromlist=["aget_user_teams"]).aget_user_teams(user_id)


async def _aget_team_members(team_id):
    return await __import__("services.team_service", fromlist=["aget_team_members"]).aget_team_members(team_id)


async def _aget_visible_assignment_members(user_id):
    members = {}
    for item in await _aget_user_teams(user_id):
        team_id = (item.get("team") or {}).get("team_id")
        if not team_id:
            continue
        for member in await _aget_team_members(team_id):
            uid = str(member.get("user_id") or "")
            if uid:
                members[uid] = member
    return list(members.values())


async def safe_assignment_confirm(update, context):
    query = update.callback_query
    if (query.data or "") != "assign_confirm_create":
        return
    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        await query.answer("فرایند ایجاد تسک منقضی شده است.", show_alert=True)
        context.user_data.clear()
        return
    if not (task.get("title") or "").strip() or task.get("priority") not in ("high", "medium", "low"):
        await query.answer("اطلاعات تسک ناقص است.", show_alert=True)
        return
    from handlers.task import assignment_callback
    await assignment_callback(update, context)
