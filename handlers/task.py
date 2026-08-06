from datetime import datetime, timedelta
import jdatetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import (
    create_task,
    get_active_tasks,
    get_task_by_id,
    change_task_status
)
from services.csv_export import build_csv_bytes
from utils.keyboard import (
    priority_keyboard,
    deadline_keyboard,
    task_action_keyboard
)
from utils.date_parse import parse_deadline_input
from handlers.search_share import handle_search_text

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


def _finalize_task(user_id, task):
    return create_task(
        user_id=user_id,
        title=task["title"],
        priority=task["priority"],
        deadline=task.get("deadline", ""),
        category=task.get("category", ""),
        tags=task.get("tags", ""),
        description=task.get("description", ""),
    )


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_task"] = {}
    context.user_data["step"] = "title"
    await update.message.reply_text("📝 عنوان تسک را وارد کنید:")


async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # search flow
    if await handle_search_text(update, context):
        return

    if "step" not in context.user_data:
        return

    step = context.user_data["step"]
    text = update.message.text
    task = context.user_data.get("new_task")
    if task is None and step != "search_query":
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
        task_id = _finalize_task(update.effective_user.id, task)
        context.user_data.clear()
        await update.message.reply_text(f"✅ تسک ثبت شد\n🆔 {task_id}")


async def priority_selected(update, context):
    query = update.callback_query
    await query.answer()
    priority = query.data.replace("priority_", "")
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
        task_id = _finalize_task(update.effective_user.id, task)
        context.user_data.clear()
        await update.message.reply_text(f"✅ تسک ثبت شد\n🆔 {task_id}")


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
    # default deadline
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
        text += f"| {index} | {priority} {task.get('title','-')} {status} |\n"
    text += (
        "\n\n📌 راهنما\n\n🔴 بالا\n🟠 متوسط\n🟢 پایین\n\n"
        "⏳ در انتظار\n🚀 در حال انجام\n✅ انجام شده\n❌ لغو شده\n"
    )
    return text


def build_full_report(tasks):
    table = "# 📊 گزارش پیگیری اقدامات\n\n"
    table += "| # | موضوع | دسته | تگ | اولویت | میلادی | شمسی | زمان | وضعیت | توضیح |\n"
    table += "|---|---|---|---|---|---|---|---|---|---|\n"

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
            f"| {index} | {task.get('title','-')} | {task.get('category') or '-'} "
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

    return (
        f"**{title}**\n\n"
        f"🆔 `{task_id}`\n"
        f"🎯 اولویت: {priority}\n"
        f"📌 وضعیت: {status}\n"
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
        InlineKeyboardButton("📥 دانلود CSV", callback_data="download_csv")
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
        await message.reply_text(
            format_task_card(task),
            reply_markup=task_action_keyboard(
                task.get("id", ""),
                task.get("status", "pending"),
            ),
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
    # use query.message as reply target
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
    keyboard.append([InlineKeyboardButton("📥 دانلود CSV", callback_data="download_csv")])

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

    if str(task.get("user_id")) != str(update.effective_user.id):
        await query.answer("شما مجاز به تغییر این تسک نیستید.", show_alert=True)
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
