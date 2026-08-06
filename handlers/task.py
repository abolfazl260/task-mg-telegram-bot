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

from services.excel_service import build_excel_bytes

from utils.keyboard import (
    priority_keyboard,
    deadline_keyboard,
    task_action_keyboard
)

PAGE_SIZE = 10


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["new_task"] = {}
    context.user_data["step"] = "title"

    await update.message.reply_text(
        "📝 عنوان تسک را وارد کنید:"
    )


async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "step" not in context.user_data:
        return

    step = context.user_data["step"]
    text = update.message.text
    task = context.user_data["new_task"]

    if step == "title":

        task["title"] = text
        context.user_data["step"] = "priority"

        await update.message.reply_text(
            "🎯 اولویت را انتخاب کنید:",
            reply_markup=priority_keyboard()
        )

        return

    if step == "deadline_custom":

        task["deadline"] = text

        context.user_data["step"] = "category"

        await update.message.reply_text(
            "📂 دسته‌بندی را وارد کنید یا /skip بزنید:"
        )

        return

    if step == "category":

        task["category"] = text

        context.user_data["step"] = "tags"

        await update.message.reply_text(
            "🏷 تگ را وارد کنید یا /skip بزنید:"
        )

        return

    if step == "tags":

        task["tags"] = text

        task_id = create_task(
            user_id=update.effective_user.id,
            title=task["title"],
            priority=task["priority"],
            deadline=task["deadline"],
            category=task.get("category", ""),
            tags=task.get("tags", "")
        )

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ تسک ثبت شد\n🆔 {task_id}"
        )


async def priority_selected(update, context):

    query = update.callback_query

    await query.answer()

    priority = query.data.replace(
        "priority_",
        ""
    )

    context.user_data["new_task"]["priority"] = priority

    await query.message.reply_text(
        "📅 زمان انجام را انتخاب کنید:",
        reply_markup=deadline_keyboard()
    )


async def deadline_selected(update, context):

    query = update.callback_query

    await query.answer()

    value = query.data.replace(
        "deadline_",
        ""
    )

    if value == "custom":

        context.user_data["step"] = "deadline_custom"

        await query.message.reply_text(
            "📅 تاریخ دقیق را وارد کنید:\nمثال: 2026-08-20"
        )

        return

    days = int(value)

    deadline = datetime.now() + timedelta(
        days=days
    )

    context.user_data["new_task"]["deadline"] = (
        deadline.strftime("%Y-%m-%d")
    )

    context.user_data["step"] = "category"

    await query.message.reply_text(
        "📂 دسته‌بندی را وارد کنید یا /skip بزنید:"
    )


async def skip_field(update: Update, context: ContextTypes.DEFAULT_TYPE):

    step = context.user_data.get("step")

    task = context.user_data.get("new_task")

    if step == "category":

        task["category"] = ""

        context.user_data["step"] = "tags"

        await update.message.reply_text(
            "🏷 تگ را وارد کنید یا /skip بزنید:"
        )

        return

    if step == "tags":

        task["tags"] = ""

        task_id = create_task(
            user_id=update.effective_user.id,
            title=task["title"],
            priority=task["priority"],
            deadline=task["deadline"],
            category="",
            tags=""
        )

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ تسک ثبت شد\n🆔 {task_id}"
        )


def sort_tasks(tasks):
    return sorted(
        tasks,
        key=lambda x: x.get(
            "deadline",
            "9999-99-99"
        )
    )


def build_detail_table(tasks, start_index=1):

    text = "# 📋 فهرست اقدامات\n\n| شماره | جزئیات |\n|---|---|\n"

    for index, task in enumerate(
        tasks,
        start=start_index
    ):

        priority = {
            "high": "🔴",
            "medium": "🟠",
            "low": "🟢"
        }.get(
            task.get("priority"),
            "🟢"
        )

        status = {
            "pending": "⏳",
            "in_progress": "🚀",
            "done": "✅",
            "cancelled": "❌"
        }.get(
            task.get("status"),
            "⏳"
        )

        text += (
            f"| {index} "
            f"| {priority} {task.get('title','-')} "
            f"{status} "
            f"|\n"
        )

    text += "\n\n📌 راهنما\n\n🔴 بالا\n🟠 متوسط\n🟢 پایین\n\n⏳ در انتظار\n🚀 در حال انجام\n✅ انجام شده\n❌ لغو شده\n"

    return text


def build_full_report(tasks):

    table = "# 📊 گزارش پیگیری اقدامات\n\n"
    table += "| # | موضوع | مسئول | دسته‌بندی | برچسب | اولویت | میلادی | شمسی | زمان | وضعیت |\n"
    table += "|---|---|---|---|---|---|---|---|---|---|\n"

    for index, task in enumerate(
        tasks,
        start=1
    ):

        priority = {
            "high": "🔴",
            "medium": "🟠",
            "low": "🟢"
        }.get(
            task.get("priority"),
            "🟢"
        )

        deadline = task.get(
            "deadline",
            "-"
        )

        try:

            deadline_date = datetime.strptime(
                deadline,
                "%Y-%m-%d"
            ).date()

            diff = (
                deadline_date -
                datetime.now().date()
            ).days

            if diff < 0:
                remaining = f"🔻{abs(diff)}"
            elif diff == 0:
                remaining = "⏰"
            elif diff <= 3:
                remaining = f"⚠️{diff}"
            else:
                remaining = f"🕒{diff}"

            jalali_date = (
                jdatetime.date
                .fromgregorian(
                    date=deadline_date
                )
                .strftime(
                    "%Y/%m/%d"
                )
            )

        except Exception:
            remaining = "-"
            jalali_date = "-"

        status = {
            "pending": "⏳ در انتظار",
            "in_progress": "🚀 در حال انجام",
            "done": "✅ انجام شده",
            "cancelled": "❌ لغو شده"
        }.get(
            task.get("status"),
            "-"
        )

        table += (
            f"| {index} "
            f"| {task.get('title','-')} "
            f"| {task.get('owner','بزودی')} "
            f"| {task.get('category','-')} "
            f"| {task.get('tags','-')} "
            f"| {priority} "
            f"| {deadline} "
            f"| {jalali_date} "
            f"| {remaining} "
            f"| {status} |\n"
        )

    return table


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    tasks = get_active_tasks(
        update.effective_user.id
    )

    if not tasks:
        await update.message.reply_text(
            "🎉 تسک فعال ندارید"
        )
        return

    tasks = sort_tasks(tasks)

    high_count = 0
    medium_count = 0
    low_count = 0

    for task in tasks:

        if task.get("priority") == "high":
            high_count += 1
        elif task.get("priority") == "medium":
            medium_count += 1
        else:
            low_count += 1

    await update.message.reply_text(
        f"\n# 🚦 وضعیت اولویت‌ها\n\n🔴 بالا\n\n{high_count} تسک\n\n"
        f"🟠 متوسط\n\n{medium_count} تسک\n\n"
        f"🟢 پایین\n\n{low_count} تسک\n"
    )

    # =====================
    # جزئیات - جدول دو ستونه (صفحه اول)
    # =====================

    first_page = tasks[:PAGE_SIZE]

    text = build_detail_table(first_page)

    keyboard = []

    if len(tasks) > PAGE_SIZE:

        keyboard.append(
            [
                InlineKeyboardButton(
                    "➡️ صفحه بعد",
                    callback_data="detail_page_2"
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "📥 دانلود اکسل",
                callback_data="download_excel"
            )
        ]
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    # =====================
    # جدول کامل همه داده ها (ریچ مسیج)
    # =====================

    table = build_full_report(tasks)

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {
                "markdown": table
            }
        }
    )

    # =====================
    # پیام‌های تعاملی با دکمه‌های عملیات برای هر تسک
    # =====================

    await update.message.reply_text(
        "⬇️ برای تغییر وضعیت هر تسک، از دکمه‌های زیر استفاده کنید:"
    )

    for task in first_page:
        priority_emoji = {
            "high": "🔴",
            "medium": "🟠",
            "low": "🟢"
        }.get(task.get("priority"), "🟢")

        status_emoji = {
            "pending": "⏳",
            "in_progress": "🚀",
            "done": "✅",
            "cancelled": "❌"
        }.get(task.get("status"), "⏳")

        title = task.get("title", "-")
        task_id = task.get("id", "")
        deadline = task.get("deadline", "-")

        caption = (
            f"{priority_emoji} {status_emoji} **{title}**\n"
            f"📅 {deadline} | 🆔 `{task_id}`"
        )

        await update.message.reply_text(
            caption,
            reply_markup=task_action_keyboard(
                task_id,
                task.get("status", "pending")
            ),
            parse_mode="Markdown"
        )


async def download_excel(update, context):

    query = update.callback_query

    await query.answer()

    buffer, count = build_excel_bytes(
        update.effective_user.id
    )

    if count == 0:
        await query.message.reply_text(
            "🎉 تسک فعالی برای دانلود ندارید"
        )
        return

    await query.message.reply_document(
        document=buffer,
        filename="tasks.xlsx",
        caption=f"📥 {count} تسک فعال"
    )


async def detail_page(update, context):

    query = update.callback_query

    await query.answer()

    try:
        page = int(
            query.data.replace(
                "detail_page_",
                ""
            )
        )
    except ValueError:
        page = 1

    tasks = get_active_tasks(
        update.effective_user.id
    )

    if not tasks:
        await query.message.reply_text(
            "🎉 تسک فعال ندارید"
        )
        return

    tasks = sort_tasks(tasks)

    total_pages = max(
        1,
        -(-len(tasks) // PAGE_SIZE)
    )

    page = min(page, total_pages)

    start_index = (
        (page - 1) * PAGE_SIZE
    ) + 1

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    page_tasks = tasks[start:end]

    text = build_detail_table(
        page_tasks,
        start_index=start_index
    )

    text += f"\n\n📄 صفحه {page} از {total_pages}"

    keyboard = []

    nav = []

    if page > 1:
        nav.append(
            InlineKeyboardButton(
                "⬅️ قبلی",
                callback_data=f"detail_page_{page - 1}"
            )
        )

    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                "➡️ بعدی",
                callback_data=f"detail_page_{page + 1}"
            )
        )

    if nav:
        keyboard.append(nav)

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =====================
# Action Handlers (شروع / انجام شد / لغو)
# =====================

STATUS_LABELS = {
    "pending": "⏳ در انتظار",
    "in_progress": "🚀 در حال انجام",
    "done": "✅ انجام شده",
    "cancelled": "❌ لغو شده",
}


async def _handle_status_change(update, context, new_status: str):

    query = update.callback_query
    await query.answer()

    # callback_data format: start_XXXX / done_XXXX / cancel_XXXX / pending_XXXX
    prefix = query.data.split("_")[0]
    task_id = query.data.replace(f"{prefix}_", "", 1)

    task = get_task_by_id(task_id)

    if not task:
        await query.edit_message_text(
            "⚠️ این تسک پیدا نشد."
        )
        return

    # security: only owner can change
    if str(task.get("user_id")) != str(update.effective_user.id):
        await query.answer("شما مجاز به تغییر این تسک نیستید.", show_alert=True)
        return

    success = change_task_status(task_id, new_status)

    if not success:
        await query.edit_message_text(
            "❌ خطا در تغییر وضعیت تسک."
        )
        return

    title = task.get("title", "-")
    label = STATUS_LABELS.get(new_status, new_status)

    # update the message to show new status and remove/hide old buttons
    await query.edit_message_text(
        f"{label}\n\n**{title}**\n🆔 `{task_id}`",
        parse_mode="Markdown"
    )

    # optional confirmation
    await query.message.reply_text(
        f"وضعیت تسک «{title}» به {label} تغییر کرد."
    )


async def start_task(update, context):
    await _handle_status_change(update, context, "in_progress")


async def done_task(update, context):
    await _handle_status_change(update, context, "done")


async def cancel_task(update, context):
    await _handle_status_change(update, context, "cancelled")


async def pending_task(update, context):
    await _handle_status_change(update, context, "pending")
