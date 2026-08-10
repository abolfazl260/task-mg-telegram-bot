from collections import Counter
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import get_all_user_tasks, get_task_by_id
from services.team_service import get_user_teams, get_team_members, member_display


def _split_tags(raw):
    if not raw:
        return []
    return [item.strip().lstrip("#") for item in str(raw).replace("\n", ",").replace("،", ",").split(",") if item.strip()]


def get_suggested_tags(user_id, limit=10):
    counts = Counter()
    display = {}
    for task in get_all_user_tasks(user_id):
        for tag in _split_tags(task.get("tags")):
            key = tag.casefold()
            counts[key] += 1
            display.setdefault(key, tag)
    return [display[key] for key, _ in counts.most_common(limit)]


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
    ids = {str(m.get("user_id")) for m in members}
    counts = Counter()
    for task in get_all_user_tasks(user_id):
        aid = str(task.get("assignee_id") or "")
        if aid in ids:
            counts[aid] += 1
    ordered = sorted(members, key=lambda m: (-counts[str(m.get("user_id"))], member_display(m)))
    return [(m, counts[str(m.get("user_id"))]) for m in ordered if counts[str(m.get("user_id"))] > 0][:limit]


def _suggested_tag_keyboard(context, user_id):
    tags = get_suggested_tags(user_id)
    context.user_data["tag_suggestions"] = tags
    rows = [[InlineKeyboardButton(f"🏷 {tag}", callback_data=f"tags_pick_{i}")] for i, tag in enumerate(tags)]
    rows.append([InlineKeyboardButton("➕ تگ جدید", callback_data="tags_new")])
    rows.append([InlineKeyboardButton("⏭ بدون تگ", callback_data="tags_skip")])
    return InlineKeyboardMarkup(rows)


def install_tag_flow(task_module):
    """Install the task-flow overrides used by the current tag/assignment UI."""
    if getattr(task_module, "_legacy_suggestions_installed", False):
        return
    task_module._legacy_suggestions_installed = True
    original_assignment_callback = task_module.assignment_callback

    async def ask_tags(message, context):
        context.user_data["step"] = "tags"
        user = getattr(message, "from_user", None)
        user_id = getattr(user, "id", 0)
        await message.reply_text(
            "🏷 تگ را انتخاب کنید یا تگ جدید را وارد کنید:",
            reply_markup=_suggested_tag_keyboard(context, user_id),
        )

    async def ask_assignment(update, context):
        context.user_data["step"] = "assignment_method"
        user_id = update.effective_user.id
        rows = [[InlineKeyboardButton("🙋 من انجام می‌دهم", callback_data="assign_self")]]
        for member, count in _top_assignees(user_id):
            rows.append([InlineKeyboardButton(f"👤 {member_display(member)} — {count} تسک", callback_data=f"assign_member_{member.get('user_id')}")])
        rows.append([InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="assign_search")])
        if get_user_teams(user_id):
            rows.append([InlineKeyboardButton("👥 انتخاب از اعضای تیم", callback_data="assign_teams")])
        rows.append([InlineKeyboardButton("⏭ بدون مسئول", callback_data="assign_none")])
        await update.effective_message.reply_text("👤 انتخاب مسئول وظیفه", reply_markup=InlineKeyboardMarkup(rows))

    async def assignment_callback(update, context):
        query = update.callback_query
        if query.data == "assign_self":
            await query.answer()
            user = update.effective_user
            task = context.user_data.setdefault("new_task", {})
            task["assignee"] = {
                "user_id": str(user.id),
                "display_name": user.full_name,
                "username": user.username or "",
            }
            await query.message.reply_text(
                task_module._assignment_summary(task),
                reply_markup=task_module._confirm_create_keyboard(),
            )
            return
        return await original_assignment_callback(update, context)

    task_module._ask_tags = ask_tags
    task_module._ask_assignment = ask_assignment
    task_module.assignment_callback = assignment_callback

    # main.py imports assignment_callback before build_application() calls this
    # hook. Refresh that module-level alias so the registered handler points to
    # the wrapped callback that actually handles assign_self.
    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.assignment_callback = assignment_callback


async def handle_tag_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("tags_"):
        return
    await query.answer()
    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        return
    if data == "tags_skip":
        task["tags"] = ""
        context.user_data.pop("tag_suggestions", None)
        from handlers.task import _ask_description
        await _ask_description(query.message, context)
        return
    if data == "tags_new":
        context.user_data["step"] = "tags"
        await query.message.reply_text("🏷 تگ جدید را وارد کنید:")
        return
    if data.startswith("tags_pick_"):
        try:
            index = int(data.replace("tags_pick_", "", 1))
        except ValueError:
            return
        tags = context.user_data.get("tag_suggestions") or []
        if 0 <= index < len(tags):
            task["tags"] = tags[index]
            context.user_data.pop("tag_suggestions", None)
            from handlers.task import _ask_description
            await _ask_description(query.message, context)


async def handle_tag_text(update, context):
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
