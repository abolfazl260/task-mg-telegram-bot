from datetime import datetime, timedelta
import logging
import jdatetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import (
    create_task,
    get_active_tasks,
    get_task_by_id,
    change_task_status,
    user_can_modify_task,
    assign_task,
    get_unassigned_tasks,
)
from services.csv_export import build_csv_bytes
from services.team_service import get_user_teams, get_team_members, member_display
from utils.keyboard import (
    priority_keyboard,
    deadline_keyboard,
    task_action_keyboard
)
from utils.date_parse import parse_deadline_input
from handlers.search_share import handle_search_text
from handlers.import_bulk import handle_import_text
from handlers.team import handle_team_text
from handlers.habits import handle_habit_text, habit_skip

logger = logging.getLogger(__name__)

PAGE_SIZE = 10

PRIORITY_LABEL = {
    "high": "🔴 بالا",
    "medium": "🟠 متوسط",
    "low": "🟢 پایین",
}

STATUS_LABEL = {
    "pending": "⏳ در انتظار",
    "in_progress": "🚀 در حال انجام",
    "done": "✅ انجام شده",
    "cancelled": "❌ لغو شده",
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _is_bare_task_id(text: str) -> bool:
    value = (text or "").strip()
    return len(value) == 8 and value.isalnum()


def _can_view_task(user_id, task: dict) -> bool:
    return any(t.get("id") == task.get("id") for t in get_active_tasks(user_id)) or user_can_modify_task(user_id, task)



async def show_task_by_id_if_matches(update, context) -> bool:
    text = (update.message.text or "").strip()
    if not _is_bare_task_id(text):
        return False
    task = get_task_by_id(text)
    if not task or not _can_view_task(update.effective_user.id, task):
        await update.message.reply_text("تسکی با این کد برای شما پیدا نشد.")
        return True
    kb = task_action_keyboard(task.get("id", ""), task.get("status", "pending")) if user_can_modify_task(update.effective_user.id, task) else None
    await update.message.reply_text(format_task_card(task), reply_markup=kb, parse_mode="Markdown")
    return True


def _finalize_task(user_id, task):
    return create_task(
        user_id=user_id,
        title=task["title"],
        priority=task["priority"],
        deadline=task.get("deadline", ""),
        category=task.get("category", ""),
        tags=task.get("tags", ""),
        description=task.get("description", ""),
        team_id=task.get("team_id", "") or "",
        assignee=task.get("assignee"),
    )


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_task"] = {}
    context.user_data["step"] = "title"
    await update.message.reply_text("📝 عنوان تسک را وارد کنید:")


async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # habit tracker text steps
    if await handle_habit_text(update, context):
        return

    # team create/join text steps
    if await handle_team_text(update, context):
        return

    # bulk import flow
    if await handle_import_text(update, context):
        return

    # assignment search flow
    if await handle_change_assignment_search_text(update, context):
        return
    if await handle_assignment_search_text(update, context):
        return

    # search flow
    if await handle_search_text(update, context):
        return

    if await show_task_by_id_if_matches(update, context):
        return

    if "step" not in context.user_data:
        return

    step = context.user_data["step"]
    text = update.message.text
    task = context.user_data.get("new_task")
    if task is None and step not in ("search_query", "import_bulk", "team_create_name", "team_join_code"):
        return

    if step == "title":
        task["title"] = text
        context.user_data["step"] = "priority"
        await update.message.reply_text(
            "🎯 اولویت را انتخاب کنید:",
            reply_markup=priority_keyboard()
        )
        return

    if step == "deadline_custom":
        parsed = parse_deadline_input(text)
        if not parsed:
            await update.message.reply_text(
                "⚠️ تاریخ نامعتبر است.\n"
                "مثال میلادی: `2026-08-20`\n"
                "مثال شمسی: `1405-05-29`",
                parse_mode="Markdown",
            )
            return
        task["deadline"] = parsed
        context.user_data["step"] = "category"
        await update.message.reply_text(
            "📂 دسته‌بندی را وارد کنید یا /skip بزنید:"
        )
        return

    if step == "category":
        task["category"] = text
        context.user_data["step"] = "tags"
        await update.message.reply_text("🏷 تگ را وارد کنید یا /skip بزنید:")
        return

    if step == "tags":
        task["tags"] = text
        context.user_data["step"] = "description"
        await update.message.reply_text(
            "📄 توضیح / یادداشت را وارد کنید یا /skip بزنید:\n(اختیاری)"
        )
        return

    if step == "description":
        task["description"] = text
        await _ask_assignment(update, context)


async def priority_selected(update, context):
    query = update.callback_query
    await query.answer()
    priority = query.data.replace("priority_", "")
    if "new_task" not in context.user_data:
        context.user_data["new_task"] = {}
    context.user_data["new_task"]["priority"] = priority
    await query.message.reply_text(
        "📅 زمان انجام را انتخاب کنید:\n(می‌توانید بدون زمان‌بندی ثبت کنید)",
        reply_markup=deadline_keyboard()
    )


async def deadline_selected(update, context):
    query = update.callback_query
    await query.answer()
    value = query.data.replace("deadline_", "")

    if value == "custom":
        context.user_data["step"] = "deadline_custom"
        await query.message.reply_text(
            "📅 تاریخ دقیق را وارد کنید:\n"
            "• میلادی: `2026-08-20`\n"
            "• شمسی: `1405-05-29`",
            parse_mode="Markdown",
        )
        return

    if value == "none":
        context.user_data["new_task"]["deadline"] = ""
        context.user_data["step"] = "category"
        await query.message.reply_text("📂 دسته‌بندی را وارد کنید یا /skip بزنید:")
        return

    days = int(value)
    deadline = datetime.now() + timedelta(days=days)
    context.user_data["new_task"]["deadline"] = deadline.strftime("%Y-%m-%d")
    context.user_data["step"] = "category"
    await query.message.reply_text("📂 دسته‌بندی را وارد کنید یا /skip بزنید:")


async def skip_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await habit_skip(update, context):
        return

    step = context.user_data.get("step")
    task = context.user_data.get("new_task")
    if not task:
        return

    if step == "category":
        task["category"] = ""
        context.user_data["step"] = "tags"
        await update.message.reply_text("🏷 تگ را وارد کنید یا /skip بزنید:")
        return

    if step == "tags":
        task["tags"] = ""
        context.user_data["step"] = "description"
        await update.message.reply_text(
            "📄 توضیح / یادداشت را وارد کنید یا /skip بزنید:\n(اختیاری)"
        )
        return

    if step == "description":
        task["description"] = ""
        await _ask_assignment(update, context)


def sort_tasks(tasks, key: str = "deadline"):
    if key == "priority":
        return sorted(
            tasks,
            key=lambda x: PRIORITY_ORDER.get(x.get("priority"), 9),
        )
    if key == "created":
        return sorted(
            tasks,
            key=lambda x: x.get("created_at") or "",
            reverse=True,
        )
    return sorted(tasks, key=lambda x: x.get("deadline") or "9999-99-99")


def build_detail_table(tasks, start_index=1):
    text = "# 📋 فهرست اقدامات\n\n| شماره | جزئیات |\n|---|---|\n"
    for index, task in enumerate(tasks, start=start_index):
        priority = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(
            task.get("priority"), "🟢"
        )
        status = {
            "pending": "⏳", "in_progress": "🚀",
            "done": "✅", "cancelled": "❌",
        }.get(task.get("status"), "⏳")
        team_mark = " 👥" if task.get("team_id") else ""
        text += f"| {index} | {priority} {task.get('title','-')} {status}{team_mark} |\n"
    text += (
        "\n\n📌 راهنما\n\n🔴 بالا\n🟠 متوسط\n🟢 پایین\n\n"
        "⏳ در انتظار\n🚀 در حال انجام\n✅ انجام شده\n❌ لغو شده\n👥 تیمی\n"
    )
    return text


def _assignee_label(task):
    name = (task.get("assignee_name") or "").strip()
    username = (task.get("assignee_username") or "").strip()
    assignee_id = (task.get("assignee_id") or "").strip()
    if name:
        return name
    if username:
        return f"@{username.lstrip('@')}"
    if assignee_id:
        return f"ID:{assignee_id}"
    return "بدون مسئول"


def build_full_report(tasks):
    table = "# 📊 گزارش پیگیری اقدامات\n\n"
    table += "| # | موضوع | مسئول | دسته | تگ | اولویت | میلادی | شمسی | زمان | وضعیت | توضیح |\n"
    table += "|---|---|---|---|---|---|---|---|---|---|---|\n"

    for index, task in enumerate(tasks, start=1):
        priority = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(
            task.get("priority"), "🟢"
        )
        deadline = task.get("deadline") or "-"
        try:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
            diff = (deadline_date - datetime.now().date()).days
            if diff < 0:
                remaining = f"🔻{abs(diff)}"
            elif diff == 0:
                remaining = "⏰"
            elif diff <= 3:
                remaining = f"⚠️{diff}"
            else:
                remaining = f"🕒{diff}"
            jalali_date = jdatetime.date.fromgregorian(
                date=deadline_date
            ).strftime("%Y/%m/%d")
        except Exception:
            remaining = "-"
            jalali_date = "-"

        status = {
            "pending": "⏳", "in_progress": "🚀",
            "done": "✅", "cancelled": "❌",
        }.get(task.get("status"), "-")
        desc = (task.get("description") or "-").replace("\n", " ")[:40]
        table += (
            f"| {index} | {task.get('title','-')} | {_assignee_label(task)} | {task.get('category') or '-'} "
            f"| {task.get('tags') or '-'} | {priority} | {deadline} "
            f"| {jalali_date} | {remaining} | {status} | {desc} |\n"
        )
    return table


def format_task_card(task: dict) -> str:
    title = task.get("title", "-")
    task_id = task.get("id", "")
    priority = PRIORITY_LABEL.get(task.get("priority"), task.get("priority", "-"))
    status = STATUS_LABEL.get(task.get("status"), task.get("status", "-"))
    deadline = task.get("deadline") or "بدون ددلاین"
    category = task.get("category") or "—"
    tags = task.get("tags") or "—"
    created = task.get("created_at") or "—"
    description = task.get("description") or "—"
    team_id = task.get("team_id") or ""

    jalali = "—"
    remaining = "—"
    if task.get("deadline"):
        try:
            deadline_date = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
            jalali = jdatetime.date.fromgregorian(
                date=deadline_date
            ).strftime("%Y/%m/%d")
            diff = (deadline_date - datetime.now().date()).days
            if diff < 0:
                remaining = f"🔻 {abs(diff)} روز گذشته"
            elif diff == 0:
                remaining = "⏰ امروز"
            elif diff <= 3:
                remaining = f"⚠️ {diff} روز مانده"
            else:
                remaining = f"🕒 {diff} روز مانده"
        except Exception:
            pass

    team_line = f"👥 تیم: `{team_id}`\n" if team_id else ""
    assignee = task.get("assignee_name") or "❌ تعیین نشده"

    return (
        f"**{title}**\n\n"
        f"🆔 `{task_id}`\n"
        f"{team_line}"
        f"🎯 اولویت: {priority}\n"
        f"📌 وضعیت: {status}\n"
        f"👤 مسئول: 🖼 {assignee}\n"
        f"📅 مهلت: {deadline}\n"
        f"🗓️ شمسی: {jalali}\n"
        f"⏳ باقی‌مانده: {remaining}\n"
        f"📂 دسته: {category}\n"
        f"🏷 تگ: {tags}\n"
        f"📄 توضیح: {description}\n"
        f"🕐 ثبت: {created}"
    )


async def _render_task_list(update, context, sort_key="deadline", edit=False):
    message = update.effective_message
    tasks = get_active_tasks(update.effective_user.id)

    if not tasks:
        await message.reply_text("🎉 تسک فعال ندارید")
        return

    tasks = sort_tasks(tasks, sort_key)
    context.user_data["tasks_sort"] = sort_key

    high_count = medium_count = low_count = 0
    for task in tasks:
        if task.get("priority") == "high":
            high_count += 1
        elif task.get("priority") == "medium":
            medium_count += 1
        else:
            low_count += 1

    sort_label = {
        "deadline": "ددلاین",
        "priority": "اولویت",
        "created": "تاریخ ایجاد",
    }.get(sort_key, sort_key)

    await message.reply_text(
        f"\n# 🚦 وضعیت اولویت‌ها\n\n"
        f"🔴 بالا — {high_count}\n"
        f"🟠 متوسط — {medium_count}\n"
        f"🟢 پایین — {low_count}\n\n"
        f"🔀 مرتب‌سازی فعلی: **{sort_label}**",
        parse_mode="Markdown",
    )

    first_page = tasks[:PAGE_SIZE]
    text = build_detail_table(first_page)

    keyboard = [
        [
            InlineKeyboardButton("📅 ددلاین", callback_data="sort_deadline"),
            InlineKeyboardButton("🎯 اولویت", callback_data="sort_priority"),
            InlineKeyboardButton("🕐 ایجاد", callback_data="sort_created"),
        ]
    ]
    if len(tasks) > PAGE_SIZE:
        keyboard.append([
            InlineKeyboardButton("➡️ صفحه بعد", callback_data="detail_page_2")
        ])
    keyboard.append([
        InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")
    ])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    table = build_full_report(tasks)
    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"markdown": table},
        },
    )

    await message.reply_text("⬇️ جزئیات کامل هر تسک + دکمه‌های تغییر وضعیت:")

    for task in first_page:
        # viewers of team tasks still see cards; action buttons only if can modify
        can_mod = user_can_modify_task(update.effective_user.id, task)
        kb = task_action_keyboard(
            task.get("id", ""),
            task.get("status", "pending"),
        ) if can_mod else None
        await message.reply_text(
            format_task_card(task),
            reply_markup=kb,
            parse_mode="Markdown",
        )


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sort_key = context.user_data.get("tasks_sort", "deadline")
    await _render_task_list(update, context, sort_key=sort_key)


async def sort_tasks_callback(update, context):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("sort_", "")
    if key not in ("deadline", "priority", "created"):
        key = "deadline"
    await _render_task_list(update, context, sort_key=key)


async def download_csv(update, context):
    query = update.callback_query
    await query.answer()
    buffer, count = build_csv_bytes(update.effective_user.id)
    if count == 0:
        await query.message.reply_text("🎉 تسک فعالی برای دانلود ندارید")
        return
    await query.message.reply_document(
        document=buffer,
        filename="tasks.csv",
        caption=f"📥 {count} تسک فعال (فرمت CSV)",
    )


async def detail_page(update, context):
    query = update.callback_query
    await query.answer()
    try:
        page = int(query.data.replace("detail_page_", ""))
    except ValueError:
        page = 1

    tasks = get_active_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("🎉 تسک فعال ندارید")
        return

    sort_key = context.user_data.get("tasks_sort", "deadline")
    tasks = sort_tasks(tasks, sort_key)
    total_pages = max(1, -(-len(tasks) // PAGE_SIZE))
    page = min(page, total_pages)
    start_index = ((page - 1) * PAGE_SIZE) + 1
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_tasks = tasks[start:end]

    text = build_detail_table(page_tasks, start_index=start_index)
    text += f"\n\n📄 صفحه {page} از {total_pages}"

    keyboard = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"detail_page_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"detail_page_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


STATUS_LABELS = {
    "pending": "⏳ در انتظار",
    "in_progress": "🚀 در حال انجام",
    "done": "✅ انجام شده",
    "cancelled": "❌ لغو شده",
}


async def _handle_status_change(update, context, new_status: str):
    query = update.callback_query
    await query.answer()
    prefix = query.data.split("_")[0]
    task_id = query.data.replace(f"{prefix}_", "", 1)
    task = get_task_by_id(task_id)

    if not task:
        await query.edit_message_text("⚠️ این تسک پیدا نشد.")
        return

    if not user_can_modify_task(update.effective_user.id, task):
        await query.answer(
            "شما مجاز به تغییر این تسک نیستید (مشاهده‌کننده یا غیرعضو).",
            show_alert=True,
        )
        return

    success = change_task_status(task_id, new_status)
    if not success:
        await query.edit_message_text("❌ خطا در تغییر وضعیت تسک.")
        return

    task["status"] = new_status
    if new_status == "done":
        task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    label = STATUS_LABELS.get(new_status, new_status)

    await query.edit_message_text(format_task_card(task), parse_mode="Markdown")
    logger.info("task_status_changed task_id=%s user_id=%s new_status=%s", task_id, update.effective_user.id, new_status)
    await query.message.reply_text(
        f"وضعیت تسک «{task.get('title', '-')}» به {label} تغییر کرد."
    )


async def start_task(update, context):
    await _handle_status_change(update, context, "in_progress")


async def done_task(update, context):
    await _handle_status_change(update, context, "done")


async def cancel_task(update, context):
    await _handle_status_change(update, context, "cancelled")


async def pending_task(update, context):
    await _handle_status_change(update, context, "pending")


def _member_key(member):
    return str(member.get("user_id") or "")


def _visible_assignment_members(user_id):
    members = {}
    for item in get_user_teams(user_id):
        for member in get_team_members(item["team"]["team_id"]):
            members[_member_key(member)] = member
    return list(members.values())


def _assignment_methods_keyboard(prefix="assign"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 جستجوی کاربر", callback_data=f"{prefix}_search")],
        [InlineKeyboardButton("👥 انتخاب از اعضای تیم", callback_data=f"{prefix}_teams")],
        [InlineKeyboardButton("⏭ بدون مسئول", callback_data=f"{prefix}_none")],
    ])


def _assignment_summary(task):
    assignee = task.get("assignee") or {}
    assignee_name = assignee.get("display_name") or task.get("assignee_name") or "❌ تعیین نشده"
    return (
        "📋 خلاصه وظیفه\n\n"
        f"عنوان:\n{task.get('title', '-')}\n\n"
        f"👤 مسئول:\n{assignee_name}\n\n"
        f"⭐ اولویت:\n{PRIORITY_LABEL.get(task.get('priority'), task.get('priority', '-'))}\n\n"
        f"⏰ مهلت:\n{task.get('deadline') or 'بدون مهلت'}\n\n"
        "آیا تایید می‌کنید؟"
    )


def _confirm_create_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و ثبت", callback_data="assign_confirm_create")],
        [InlineKeyboardButton("🔄 تغییر مسئول", callback_data="assign_change_create")],
        [InlineKeyboardButton("❌ لغو", callback_data="assign_cancel_create")],
    ])


async def _ask_assignment(update, context):
    context.user_data["step"] = "assignment_method"
    await update.effective_message.reply_text(
        "👤 انتخاب مسئول وظیفه",
        reply_markup=_assignment_methods_keyboard("assign"),
    )


async def _notify_assignment(context, task, assignee, creator):
    uid = assignee.get("user_id")
    if not uid:
        return
    creator_name = creator.full_name if creator else "—"
    text = (
        "🔔 وظیفه جدید به شما اختصاص داده شد\n\n"
        f"📌 عنوان:\n{task.get('title', '-')}\n\n"
        f"👤 ایجاد کننده:\n{creator_name}\n\n"
        f"⭐ اولویت:\n{PRIORITY_LABEL.get(task.get('priority'), task.get('priority', '-'))}\n\n"
        f"⏰ مهلت:\n{task.get('deadline') or 'بدون مهلت'}\n\n"
        "وضعیت:\n⏳ منتظر شروع"
    )
    try:
        await context.bot.send_message(chat_id=uid, text=text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("مشاهده وظیفه", callback_data=f"assignee_view_{task.get('id')}")],
            [InlineKeyboardButton("شروع کار", callback_data=f"start_{task.get('id')}")],
        ]))
    except Exception:
        pass


async def assignment_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = update.effective_user.id

    if data == "assign_search":
        context.user_data["step"] = "assignment_search"
        await query.message.reply_text("نام یا نام خانوادگی کاربر را وارد کنید:")
        return
    if data == "assign_teams":
        teams = get_user_teams(uid)
        if not teams:
            await query.message.reply_text("تیم مشترکی برای انتخاب مسئول ندارید.")
            return
        kb = [[InlineKeyboardButton(f"📌 {i['team']['name']}", callback_data=f"assign_team_{i['team']['team_id']}")] for i in teams]
        await query.message.reply_text("انتخاب گروه مشترک:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("assign_team_"):
        team_id = data.replace("assign_team_", "")
        members = get_team_members(team_id)
        kb = [[InlineKeyboardButton(f"🖼 {member_display(m)}", callback_data=f"assign_member_{m.get('user_id')}")] for m in members]
        await query.message.reply_text("اعضای این تیم:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("assign_member_"):
        mid = data.replace("assign_member_", "")
        member = next((m for m in _visible_assignment_members(uid) if _member_key(m) == mid), None)
        if not member:
            await query.message.reply_text("کاربر انتخاب‌شده در تیم مشترک پیدا نشد.")
            return
        context.user_data.setdefault("new_task", {})["assignee"] = member
        await query.message.reply_text(_assignment_summary(context.user_data["new_task"]), reply_markup=_confirm_create_keyboard())
        return
    if data == "assign_none":
        context.user_data.setdefault("new_task", {})["assignee"] = None
        await query.message.reply_text(_assignment_summary(context.user_data["new_task"]), reply_markup=_confirm_create_keyboard())
        return
    if data == "assign_change_create":
        await _ask_assignment(update, context)
        return
    if data == "assign_cancel_create":
        context.user_data.clear()
        await query.message.reply_text("❌ ایجاد تسک لغو شد.")
        return
    if data == "assign_confirm_create":
        task = context.user_data.get("new_task") or {}
        task_id = _finalize_task(uid, task)
        saved = get_task_by_id(task_id)
        assignee = task.get("assignee")
        context.user_data.clear()
        logger.info("task_created task_id=%s user_id=%s assignee_id=%s team_id=%s", task_id, uid, (assignee or {}).get("user_id") or "", task.get("team_id", ""))
        await query.message.reply_text(f"✅ تسک ثبت شد\n🆔 {task_id}")
        if assignee:
            await _notify_assignment(context, saved or task, assignee, update.effective_user)
        return


async def handle_assignment_search_text(update, context):
    if context.user_data.get("step") != "assignment_search":
        return False
    q = (update.message.text or "").strip().lower()
    matches = []
    for m in _visible_assignment_members(update.effective_user.id):
        blob = f"{m.get('display_name','')} {m.get('username','')}".lower()
        if q and q in blob:
            matches.append(m)
    if not matches:
        await update.message.reply_text("نتیجه‌ای در تیم‌های مشترک پیدا نشد.")
        return True
    kb = []
    for m in matches[:10]:
        uname = f"\n@{m.get('username')}" if m.get("username") else ""
        await update.message.reply_text(f"🖼\n{m.get('display_name') or 'کاربر'}{uname}")
        kb.append([InlineKeyboardButton(f"انتخاب مسئول: {member_display(m)}", callback_data=f"assign_member_{m.get('user_id')}")])
    await update.message.reply_text("👤 نتایج جستجو", reply_markup=InlineKeyboardMarkup(kb))
    return True


async def unassigned_tasks(update, context):
    tasks = sort_tasks(get_unassigned_tasks(update.effective_user.id), "created")
    if not tasks:
        await update.effective_message.reply_text("وظیفه بدون مسئول ندارید.")
        return
    offset = context.user_data.get("unassigned_offset", 0)
    if offset >= len(tasks):
        offset = 0
    page_tasks = tasks[offset:offset + PAGE_SIZE]
    context.user_data["unassigned_offset"] = offset + len(page_tasks)
    await update.effective_message.reply_text(
        f"📋 وظایف بدون مسئول: {len(tasks)} مورد\n"
        f"نمایش {offset + 1} تا {offset + len(page_tasks)} با توضیحات کامل."
    )
    for task in page_tasks:
        await update.effective_message.reply_text(
            format_task_card(task),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🙋 برعهده گرفتن", callback_data=f"take_{task.get('id')}")]]),
            parse_mode="Markdown",
        )
    remaining = len(tasks) - context.user_data.get("unassigned_offset", 0)
    if remaining > 0:
        await update.effective_message.reply_text(
            f"➡️ {remaining} وظیفه دیگر باقی مانده است. برای دیدن سری بعدی دوباره /unassigned را انتخاب کنید."
        )
    else:
        context.user_data["unassigned_offset"] = 0


async def take_assignment(update, context):
    query = update.callback_query
    await query.answer()
    task_id = query.data.replace("take_", "")
    task = get_task_by_id(task_id)
    if not task:
        await query.message.reply_text("تسک پیدا نشد.")
        return
    if task.get("assignee_id"):
        await query.message.reply_text("این تسک قبلاً مسئول دارد.")
        return
    context.user_data["take_task_id"] = task_id
    await query.message.reply_text(
        f"آیا این وظیفه را برای خودتان انتخاب می‌کنید؟\n\nوظیفه:\n{task.get('title')}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ بله، مسئول می‌شوم", callback_data="take_confirm")],[InlineKeyboardButton("❌ لغو", callback_data="take_cancel")]])
    )


async def take_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "take_cancel":
        context.user_data.pop("take_task_id", None)
        await query.message.reply_text("لغو شد.")
        return
    task_id = context.user_data.pop("take_task_id", "")
    user = update.effective_user
    member = {"user_id": str(user.id), "display_name": user.full_name, "username": user.username or ""}
    if assign_task(task_id, member, user.id, "taken"):
        await query.message.reply_text("✅ این وظیفه به شما اختصاص داده شد.")
    else:
        await query.message.reply_text("❌ خطا در تخصیص وظیفه.")


def _history_text(task):
    lines = ["📜 تاریخچه", "", task.get("created_at") or "", "وظیفه ایجاد شد"]
    for raw in (task.get("assignment_history") or "").splitlines():
        parts = raw.split("|", 4)
        if len(parts) != 5:
            continue
        when, _actor, action, old, new = parts
        lines += ["", when]
        if action == "changed":
            lines += ["مسئول تغییر کرد:", f"از: {old}", f"به: {new}"]
        elif action == "removed":
            lines += ["مسئول حذف شد:", old]
        elif action == "taken":
            lines += ["مسئول تعیین شد:", new]
        else:
            lines += ["مسئول تعیین شد:", new]
    return "\n".join(lines)


async def assignment_manage_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = update.effective_user.id
    if data.startswith("owner_"):
        task_id = data.replace("owner_", "")
        task = get_task_by_id(task_id)
        if not task:
            await query.message.reply_text("تسک پیدا نشد.")
            return
        current = task.get("assignee_name") or "❌ تعیین نشده"
        kb = [
            [InlineKeyboardButton("🔄 تغییر مسئول", callback_data=f"chg_start_{task_id}")],
            [InlineKeyboardButton("🙋 برعهده گرفتن", callback_data=f"take_{task_id}")],
            [InlineKeyboardButton("❌ حذف مسئول", callback_data=f"asg_remove_{task_id}")],
            [InlineKeyboardButton("📜 تاریخچه", callback_data=f"asg_history_{task_id}")],
        ]
        await query.message.reply_text(f"📋 اطلاعات مسئول\n\nمسئول فعلی:\n🖼 {current}\n\nعملیات:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("asg_history_"):
        task = get_task_by_id(data.replace("asg_history_", ""))
        await query.message.reply_text(_history_text(task) if task else "تسک پیدا نشد.")
        return
    if data.startswith("asg_remove_"):
        task_id = data.replace("asg_remove_", "")
        task = get_task_by_id(task_id)
        if not user_can_modify_task(uid, task):
            await query.message.reply_text("شما مجاز به تغییر مسئول نیستید.")
            return
        assign_task(task_id, None, uid, "removed")
        await query.message.reply_text("✅ مسئول حذف شد.")
        return
    if data.startswith("chg_start_"):
        task_id = data.replace("chg_start_", "")
        context.user_data["change_task_id"] = task_id
        await query.message.reply_text("👤 انتخاب مسئول جدید", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="chg_search")],
            [InlineKeyboardButton("👥 انتخاب از اعضای تیم", callback_data="chg_teams")],
        ]))
        return
    if data == "chg_search":
        context.user_data["step"] = "change_assignment_search"
        await query.message.reply_text("نام یا نام خانوادگی کاربر را وارد کنید:")
        return
    if data == "chg_teams":
        kb = [[InlineKeyboardButton(f"📌 {i['team']['name']}", callback_data=f"chg_team_{i['team']['team_id']}")] for i in get_user_teams(uid)]
        await query.message.reply_text("انتخاب گروه مشترک:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("chg_team_"):
        members = get_team_members(data.replace("chg_team_", ""))
        kb = [[InlineKeyboardButton(f"🖼 {member_display(m)}", callback_data=f"chg_member_{m.get('user_id')}")] for m in members]
        await query.message.reply_text("اعضای این تیم:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("chg_member_"):
        mid = data.replace("chg_member_", "")
        member = next((m for m in _visible_assignment_members(uid) if _member_key(m) == mid), None)
        if not member:
            await query.message.reply_text("کاربر پیدا نشد.")
            return
        context.user_data["change_assignee"] = member
        await query.message.reply_text(
            f"مسئول جدید:\n\n🖼 {member_display(member)}\n\nآیا تغییر داده شود؟",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید تغییر", callback_data="chg_confirm")],[InlineKeyboardButton("❌ لغو", callback_data="chg_cancel")]])
        )
        return
    if data == "chg_cancel":
        context.user_data.pop("change_task_id", None)
        context.user_data.pop("change_assignee", None)
        await query.message.reply_text("لغو شد.")
        return
    if data == "chg_confirm":
        task_id = context.user_data.pop("change_task_id", "")
        assignee = context.user_data.pop("change_assignee", None)
        task = get_task_by_id(task_id)
        if not user_can_modify_task(uid, task):
            await query.message.reply_text("شما مجاز به تغییر مسئول نیستید.")
            return
        if assign_task(task_id, assignee, uid, "changed"):
            saved = get_task_by_id(task_id)
            await query.message.reply_text("✅ مسئول تغییر کرد.")
            await _notify_assignment(context, saved, assignee, update.effective_user)
        else:
            await query.message.reply_text("❌ خطا در تغییر مسئول.")


async def handle_change_assignment_search_text(update, context):
    if context.user_data.get("step") != "change_assignment_search":
        return False
    q = (update.message.text or "").strip().lower()
    matches = [m for m in _visible_assignment_members(update.effective_user.id) if q in f"{m.get('display_name','')} {m.get('username','')}".lower()]
    if not matches:
        await update.message.reply_text("نتیجه‌ای در تیم‌های مشترک پیدا نشد.")
        return True
    kb = [[InlineKeyboardButton(f"انتخاب مسئول: {member_display(m)}", callback_data=f"chg_member_{m.get('user_id')}")] for m in matches[:10]]
    await update.message.reply_text("👤 نتایج جستجو", reply_markup=InlineKeyboardMarkup(kb))
    return True
