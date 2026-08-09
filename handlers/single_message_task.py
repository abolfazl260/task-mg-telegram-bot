from collections import Counter
from datetime import datetime, timedelta
import jdatetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import create_task, get_all_user_tasks, get_task_by_id
from services.team_service import get_user_teams, get_team_members, member_display
from utils.date_parse import parse_deadline_input
from utils.keyboard import priority_keyboard, deadline_keyboard
from handlers.tag_suggestions import get_suggested_tags

PRIORITY_LABEL = {
    "high": "🔴 بالا",
    "medium": "🟠 متوسط",
    "low": "🟢 پایین",
}


def _state(context):
    return context.user_data.setdefault("new_task", {})


def _flow_message_id(context):
    return context.user_data.get("single_message_id")


def _date_pair(value):
    if not value:
        return "بدون مهلت"
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
        jalali = jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")
        return f"{value} / {jalali}"
    except Exception:
        return str(value)


def _date_choice_label(value):
    if value == "":
        return "بدون مهلت"
    return _date_pair(value)


async def _edit_flow(context, text, keyboard=None, message=None):
    target = message
    if target is None:
        message_id = _flow_message_id(context)
        if message_id:
            try:
                target = await context.bot.edit_message_text(
                    chat_id=context.user_data.get("single_chat_id"),
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                )
                return target
            except Exception:
                return None
    if target is not None:
        try:
            await target.edit_text(text=text, reply_markup=keyboard)
            return target
        except Exception:
            try:
                await target.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
    return None


def _title_screen():
    return "📋 افزودن تسک\n\nعنوان تسک را وارد کنید:"


def _priority_screen(task):
    title = task.get("title") or "—"
    return f"📋 افزودن تسک\n\nعنوان: {title}\n\nحالا اولویت را انتخاب کنید:"


def _deadline_screen(task):
    title = task.get("title") or "—"
    priority = PRIORITY_LABEL.get(task.get("priority"), "—")
    return (
        "📋 افزودن تسک\n\n"
        f"عنوان: {title}\n"
        f"اولویت: {priority}\n\n"
        "مهلت را انتخاب کنید:"
    )


def _category_keyboard(user_id):
    seen = set()
    categories = []
    for task in get_all_user_tasks(user_id):
        category = (task.get("category") or "").strip()
        key = category.casefold()
        if category and key not in seen:
            seen.add(key)
            categories.append(category)
    rows = [[InlineKeyboardButton(f"📂 {c}", callback_data=f"sm_category_{i}")] for i, c in enumerate(categories[:12])]
    rows.append([InlineKeyboardButton("⏭ رد کردن", callback_data="sm_category_skip")])
    return InlineKeyboardMarkup(rows), categories[:12]


def _category_screen(task):
    return (
        "📋 افزودن تسک\n\n"
        f"عنوان: {task.get('title') or '—'}\n"
        f"اولویت: {PRIORITY_LABEL.get(task.get('priority'), '—')}\n"
        f"مهلت: {_date_pair(task.get('deadline'))}\n\n"
        "دسته‌بندی را انتخاب کنید یا نام دسته‌بندی جدید را ارسال کنید:"
    )


def _tags_keyboard(user_id, context):
    tags = get_suggested_tags(user_id, limit=10)
    context.user_data["single_tag_suggestions"] = tags
    rows = [[InlineKeyboardButton(f"🏷 {tag}", callback_data=f"sm_tag_{i}")] for i, tag in enumerate(tags)]
    rows.append([InlineKeyboardButton("➕ تگ جدید", callback_data="sm_tag_new")])
    rows.append([InlineKeyboardButton("⏭ بدون تگ", callback_data="sm_tag_skip")])
    return InlineKeyboardMarkup(rows)


def _tags_screen(task):
    return (
        "📋 افزودن تسک\n\n"
        f"عنوان: {task.get('title') or '—'}\n"
        f"اولویت: {PRIORITY_LABEL.get(task.get('priority'), '—')}\n"
        f"مهلت: {_date_pair(task.get('deadline'))}\n"
        f"دسته‌بندی: {task.get('category') or '—'}\n\n"
        "تگ را انتخاب کنید یا تگ جدید را ارسال کنید:"
    )


def _description_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ بدون توضیح", callback_data="sm_description_skip")]])


def _description_screen(task):
    return (
        "📋 افزودن تسک\n\n"
        f"عنوان: {task.get('title') or '—'}\n"
        f"اولویت: {PRIORITY_LABEL.get(task.get('priority'), '—')}\n"
        f"مهلت: {_date_pair(task.get('deadline'))}\n"
        f"دسته‌بندی: {task.get('category') or '—'}\n"
        f"تگ: {task.get('tags') or '—'}\n\n"
        "توضیح یا یادداشت را وارد کنید:"
    )


def _visible_members(user_id):
    members = {}
    for item in get_user_teams(user_id):
        team_id = item.get("team", {}).get("team_id")
        if not team_id:
            continue
        for member in get_team_members(team_id):
            key = str(member.get("user_id") or "")
            if key:
                members[key] = member
    return list(members.values())


def _top_assignees(user_id, members, limit=3):
    member_ids = {str(m.get("user_id")) for m in members}
    counts = Counter()
    for task in get_all_user_tasks(user_id):
        aid = str(task.get("assignee_id") or "")
        if aid in member_ids:
            counts[aid] += 1
    ordered = sorted(members, key=lambda m: (-counts[str(m.get("user_id"))], member_display(m)))
    return [(m, counts[str(m.get("user_id"))]) for m in ordered[:limit] if counts[str(m.get("user_id"))] > 0]


def _assignment_keyboard(user_id):
    members = _visible_members(user_id)
    rows = [[InlineKeyboardButton("🙋 من انجام می‌دهم", callback_data="sm_assign_self")]]
    for member, count in _top_assignees(user_id, members):
        rows.append([InlineKeyboardButton(f"👤 {member_display(member)} — {count} تسک", callback_data=f"sm_assign_{member.get('user_id')}")])
    rows.append([InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="sm_assign_search")])
    if get_user_teams(user_id):
        rows.append([InlineKeyboardButton("👥 انتخاب از اعضای تیم", callback_data="sm_assign_teams")])
    rows.append([InlineKeyboardButton("⏭ بدون مسئول", callback_data="sm_assign_none")])
    return InlineKeyboardMarkup(rows)


def _assignment_screen(task):
    return (
        "📋 افزودن تسک\n\n"
        f"عنوان: {task.get('title') or '—'}\n"
        f"اولویت: {PRIORITY_LABEL.get(task.get('priority'), '—')}\n"
        f"مهلت: {_date_pair(task.get('deadline'))}\n"
        f"دسته‌بندی: {task.get('category') or '—'}\n"
        f"تگ: {task.get('tags') or '—'}\n"
        f"توضیح: {task.get('description') or '—'}\n\n"
        "👤 انتخاب مسئول وظیفه"
    )


def _summary_screen(task):
    assignee = task.get("assignee") or {}
    assignee_name = assignee.get("display_name") or "بدون مسئول"
    return (
        "📋 بررسی نهایی تسک\n\n"
        f"📌 عنوان: {task.get('title') or '—'}\n"
        f"⭐ اولویت: {PRIORITY_LABEL.get(task.get('priority'), '—')}\n"
        f"📅 مهلت: {_date_pair(task.get('deadline'))}\n"
        f"📂 دسته‌بندی: {task.get('category') or '—'}\n"
        f"🏷 تگ: {task.get('tags') or '—'}\n"
        f"📄 توضیح: {task.get('description') or '—'}\n"
        f"👤 مسئول: {assignee_name}\n\n"
        "تسک آماده ثبت است."
    )


def _summary_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت تسک", callback_data="sm_confirm")],
        [InlineKeyboardButton("🔄 تغییر مسئول", callback_data="sm_assign_back")],
        [InlineKeyboardButton("❌ لغو", callback_data="sm_cancel")],
    ])


async def add_task(update, context):
    context.user_data.pop("new_task", None)
    context.user_data["new_task"] = {}
    context.user_data["single_chat_id"] = update.effective_chat.id
    context.user_data["single_step"] = "title"
    msg = await update.message.reply_text(_title_screen())
    context.user_data["single_message_id"] = msg.message_id


async def save_task(update, context):
    step = context.user_data.get("single_step")
    if not step:
        return False
    task = _state(context)
    text = (update.effective_message.text or "").strip()
    if not text:
        return True

    if step == "title":
        task["title"] = text
        context.user_data["single_step"] = "priority"
        context.user_data["step"] = "priority"
        await _edit_flow(context, _priority_screen(task), priority_keyboard(), update.effective_message)
        return True

    if step == "deadline_custom":
        parsed = parse_deadline_input(text)
        if not parsed:
            await _edit_flow(context, _deadline_screen(task) + "\n\n⚠️ تاریخ نامعتبر است. نمونه: 2026-08-20 یا 1405-05-29")
            return True
        task["deadline"] = parsed
        await _show_category(update, context)
        return True

    if step == "category":
        task["category"] = text[:100]
        await _show_tags(update, context)
        return True

    if step == "tags":
        task["tags"] = text[:120]
        await _show_description(update, context)
        return True

    if step == "description":
        task["description"] = text[:1000]
        await _show_assignment(update, context)
        return True

    if step == "assignment_search":
        await _show_assignment_search_results(update, context, text)
        return True

    return False


async def _show_category(update, context):
    context.user_data["single_step"] = "category"
    context.user_data["step"] = "category"
    kb, categories = _category_keyboard(update.effective_user.id)
    context.user_data["single_categories"] = categories
    await _edit_flow(context, _category_screen(_state(context)), kb, update.effective_message)


async def _show_tags(update, context):
    context.user_data["single_step"] = "tags"
    context.user_data["step"] = "tags"
    await _edit_flow(context, _tags_screen(_state(context)), _tags_keyboard(update.effective_user.id, context), update.effective_message)


async def _show_description(update, context):
    context.user_data["single_step"] = "description"
    context.user_data["step"] = "description"
    await _edit_flow(context, _description_screen(_state(context)), _description_keyboard(), update.effective_message)


async def _show_assignment(update, context):
    context.user_data["single_step"] = "assignment_method"
    context.user_data["step"] = "assignment_method"
    await _edit_flow(context, _assignment_screen(_state(context)), _assignment_keyboard(update.effective_user.id), update.effective_message)


async def priority_selected(update, context):
    query = update.callback_query
    await query.answer()
    task = _state(context)
    priority = (query.data or "").replace("priority_", "", 1)
    if priority not in PRIORITY_LABEL:
        return
    task["priority"] = priority
    context.user_data["single_step"] = "deadline"
    context.user_data["step"] = "deadline"
    await _edit_flow(context, _deadline_screen(task), deadline_keyboard(), query.message)


async def deadline_selected(update, context):
    query = update.callback_query
    await query.answer()
    task = _state(context)
    value = (query.data or "").replace("deadline_", "", 1)
    if value == "custom":
        context.user_data["single_step"] = "deadline_custom"
        context.user_data["step"] = "deadline_custom"
        await _edit_flow(context, _deadline_screen(task) + "\n\nتاریخ را به صورت شمسی یا میلادی ارسال کنید.\nنمونه: 1405-05-29 / 2026-08-20", None, query.message)
        return
    if value == "none":
        task["deadline"] = ""
    else:
        days = int(value)
        task["deadline"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    await _show_category(update, context)


async def callback(update, context):
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("sm_"):
        return False
    await query.answer()
    task = _state(context)

    if data == "sm_category_skip":
        task["category"] = ""
        await _show_tags(update, context)
        return True
    if data.startswith("sm_category_"):
        try:
            index = int(data.replace("sm_category_", "", 1))
            task["category"] = (context.user_data.get("single_categories") or [])[index]
        except (ValueError, IndexError):
            return True
        await _show_tags(update, context)
        return True

    if data == "sm_tag_skip":
        task["tags"] = ""
        await _show_description(update, context)
        return True
    if data == "sm_tag_new":
        context.user_data["single_step"] = "tags"
        await _edit_flow(context, _tags_screen(task) + "\n\nتگ جدید را ارسال کنید.", None, query.message)
        return True
    if data.startswith("sm_tag_"):
        try:
            index = int(data.replace("sm_tag_", "", 1))
            task["tags"] = (context.user_data.get("single_tag_suggestions") or [])[index]
        except (ValueError, IndexError):
            return True
        await _show_description(update, context)
        return True

    if data == "sm_description_skip":
        task["description"] = ""
        await _show_assignment(update, context)
        return True

    if data == "sm_assign_self":
        user = update.effective_user
        task["assignee"] = {"user_id": str(user.id), "display_name": user.full_name, "username": user.username or ""}
        await _edit_flow(context, _summary_screen(task), _summary_keyboard(), query.message)
        return True

    if data.startswith("sm_assign_") and data not in ("sm_assign_search", "sm_assign_teams", "sm_assign_self", "sm_assign_none"):
        member_id = data.replace("sm_assign_", "", 1)
        member = next((m for m in _visible_members(update.effective_user.id) if str(m.get("user_id")) == member_id), None)
        if member:
            task["assignee"] = member
            await _edit_flow(context, _summary_screen(task), _summary_keyboard(), query.message)
        return True

    if data == "sm_assign_none":
        task["assignee"] = None
        await _edit_flow(context, _summary_screen(task), _summary_keyboard(), query.message)
        return True

    if data == "sm_assign_search":
        context.user_data["single_step"] = "assignment_search"
        context.user_data["step"] = "assignment_search"
        await _edit_flow(context, _assignment_screen(task) + "\n\nنام یا نام خانوادگی کاربر را ارسال کنید:", None, query.message)
        return True

    if data == "sm_assign_teams":
        teams = get_user_teams(update.effective_user.id)
        rows = [[InlineKeyboardButton(f"📌 {i['team']['name']}", callback_data=f"sm_team_{i['team']['team_id']}")] for i in teams]
        await _edit_flow(context, _assignment_screen(task) + "\n\nتیم را انتخاب کنید:", InlineKeyboardMarkup(rows), query.message)
        return True

    if data.startswith("sm_team_"):
        team_id = data.replace("sm_team_", "", 1)
        members = get_team_members(team_id)
        rows = [[InlineKeyboardButton(f"👤 {member_display(m)}", callback_data=f"sm_assign_{m.get('user_id')}")] for m in members]
        await _edit_flow(context, _assignment_screen(task) + "\n\nعضو تیم را انتخاب کنید:", InlineKeyboardMarkup(rows), query.message)
        return True

    if data == "sm_assign_back":
        await _show_assignment(update, context)
        return True

    if data == "sm_cancel":
        context.user_data.clear()
        await _edit_flow(context, "❌ ایجاد تسک لغو شد.", None, query.message)
        return True

    if data == "sm_confirm":
        user_id = update.effective_user.id
        task_id = create_task(
            user_id=user_id,
            title=task["title"],
            priority=task["priority"],
            deadline=task.get("deadline", ""),
            category=task.get("category", ""),
            tags=task.get("tags", ""),
            description=task.get("description", ""),
            team_id=task.get("team_id", ""),
            assignee=task.get("assignee"),
        )
        saved = get_task_by_id(task_id) or task.copy()
        assignee = task.get("assignee")
        done_text = (
            "✅ تسک با موفقیت ایجاد شد\n\n"
            f"📌 {task.get('title') or '—'}\n"
            f"⭐ اولویت: {PRIORITY_LABEL.get(task.get('priority'), '—')}\n"
            f"📅 مهلت: {_date_pair(task.get('deadline'))}\n"
            f"👤 مسئول: {(assignee or {}).get('display_name') or 'بدون مسئول'}"
        )
        context.user_data.clear()
        await _edit_flow(context, done_text, None, query.message)
        if assignee and str(assignee.get("user_id")) != str(user_id):
            try:
                await context.bot.send_message(
                    chat_id=assignee.get("user_id"),
                    text=(
                        "🔔 وظیفه جدید به شما اختصاص داده شد\n\n"
                        f"📌 {saved.get('title', '-') }\n"
                        f"⭐ {PRIORITY_LABEL.get(saved.get('priority'), '-') }\n"
                        f"📅 { _date_pair(saved.get('deadline')) }"
                    ),
                )
            except Exception:
                pass
        return True
    return True


async def _show_assignment_search_results(update, context, query_text):
    q = query_text.casefold()
    matches = []
    for member in _visible_members(update.effective_user.id):
        blob = f"{member.get('display_name', '')} {member.get('username', '')}".casefold()
        if q and q in blob:
            matches.append(member)
    if not matches:
        await _edit_flow(context, _assignment_screen(_state(context)) + "\n\n❌ کاربری پیدا نشد. دوباره جستجو کنید.")
        return
    rows = [[InlineKeyboardButton(f"👤 {member_display(m)}", callback_data=f"sm_assign_{m.get('user_id')}")] for m in matches[:10]]
    await _edit_flow(context, _assignment_screen(_state(context)) + "\n\nنتایج جستجو:", InlineKeyboardMarkup(rows), update.effective_message)
