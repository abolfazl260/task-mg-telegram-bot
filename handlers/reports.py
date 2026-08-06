from datetime import datetime, date
import calendar
import jdatetime
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.task_service import get_all_user_tasks, get_active_tasks


def _priority_emoji(p):
    return {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(p, "🟢")


def _status_label(s):
    return {
        "pending": "⏳ شروع‌نشده",
        "in_progress": "🚀 در حال انجام",
        "done": "✅ انجام‌شده",
        "cancelled": "❌ رد / لغو شده",
    }.get(s, s)


def reports_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 کل تسک‌ها", callback_data="report_all")],
        [InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="report_priority")],
        [InlineKeyboardButton("📊 وضعیت تسک‌ها", callback_data="report_status")],
        [InlineKeyboardButton("📅 تقویم ماه جاری", callback_data="report_calendar")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="report_back")],
    ])


async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for reports (from menu or /reports)."""

    text = (
        "# 📊 بخش گزارشات\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(
            text,
            reply_markup=reports_menu_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reports_menu_keyboard(),
            parse_mode="Markdown"
        )


async def report_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)

    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return

    # sort by deadline
    tasks = sorted(tasks, key=lambda t: t.get("deadline", "9999-99-99"))

    table = "# 📋 گزارش کل تسک‌ها\n\n"
    table += "| # | عنوان | اولویت | وضعیت | مهلت | دسته‌بندی |\n"
    table += "|---|---|---|---|---|---|\n"

    for i, task in enumerate(tasks, start=1):
        table += (
            f"| {i} "
            f"| {task.get('title', '-')} "
            f"| {_priority_emoji(task.get('priority'))} "
            f"| {_status_label(task.get('status'))} "
            f"| {task.get('deadline', '-')} "
            f"| {task.get('category', '-') or '-'} |\n"
        )

    table += f"\n\n📌 مجموع: **{len(tasks)}** تسک"

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"markdown": table},
        },
    )


async def report_by_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)

    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return

    groups = {"high": [], "medium": [], "low": []}

    for task in tasks:
        p = task.get("priority", "low")
        if p not in groups:
            p = "low"
        groups[p].append(task)

    text = "# 🎯 گزارش بر اساس اولویت\n\n"

    for key, label, emoji in [
        ("high", "بالا", "🔴"),
        ("medium", "متوسط", "🟠"),
        ("low", "پایین", "🟢"),
    ]:
        items = groups[key]
        text += f"## {emoji} اولویت {label} — {len(items)} تسک\n\n"

        if not items:
            text += "_موردی نیست_\n\n"
            continue

        text += "| # | عنوان | وضعیت | مهلت |\n|---|---|---|---|\n"

        for i, task in enumerate(items, start=1):
            text += (
                f"| {i} "
                f"| {task.get('title', '-')} "
                f"| {_status_label(task.get('status'))} "
                f"| {task.get('deadline', '-')} |\n"
            )

        text += "\n"

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"markdown": text},
        },
    )


async def report_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)

    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return

    counts = {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "cancelled": 0,
    }

    for task in tasks:
        s = task.get("status", "pending")
        if s in counts:
            counts[s] += 1

    total = len(tasks)

    text = (
        "# 📊 وضعیت تسک‌ها\n\n"
        f"| وضعیت | تعداد | درصد |\n"
        f"|---|---|---|\n"
        f"| ⏳ شروع‌نشده | {counts['pending']} | {_pct(counts['pending'], total)} |\n"
        f"| 🚀 در حال انجام | {counts['in_progress']} | {_pct(counts['in_progress'], total)} |\n"
        f"| ✅ انجام‌شده | {counts['done']} | {_pct(counts['done'], total)} |\n"
        f"| ❌ رد / لغو شده | {counts['cancelled']} | {_pct(counts['cancelled'], total)} |\n"
        f"\n📌 **مجموع کل:** {total} تسک"
    )

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"markdown": text},
        },
    )


def _pct(n, total):
    if total == 0:
        return "0%"
    return f"{round(n / total * 100)}%"


async def report_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monthly calendar of current month with task titles."""

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)

    today = date.today()
    year, month = today.year, today.month

    # map day -> list of titles
    day_tasks = defaultdict(list)

    for task in tasks:
        deadline = task.get("deadline", "")
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
            if d.year == year and d.month == month:
                day_tasks[d.day].append(task.get("title", "-"))
        except Exception:
            continue

    # Jalali month name for title
    try:
        j_today = jdatetime.date.fromgregorian(date=today)
        j_month_name = j_today.j_months_fa[j_today.month - 1]
        j_year = j_today.year
        title_month = f"{j_month_name} {j_year}"
    except Exception:
        title_month = f"{year}/{month}"

    # build calendar table (week starts Saturday for Iran)
    # Python calendar: Monday=0 ... Sunday=6
    # We want Sat=first column
    cal = calendar.Calendar(firstweekday=5)  # Saturday

    weeks = cal.monthdayscalendar(year, month)

    text = f"# 📅 تقویم تسک‌ها — {title_month}\n\n"
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n"
    text += "|---|---|---|---|---|---|---|\n"

    for week in weeks:
        cells = []
        for day in week:
            if day == 0:
                cells.append(" ")
                continue

            cell = f"**{day}**"

            if day in day_tasks:
                titles = day_tasks[day]
                # show up to 2 titles, rest as +N
                shown = titles[:2]
                extra = len(titles) - 2
                lines = "<br>".join(shown)
                if extra > 0:
                    lines += f"<br>+{extra} مورد"
                cell = f"**{day}**<br>{lines}"

            cells.append(cell)

        text += "| " + " | ".join(cells) + " |\n"

    # list of tasks this month under the calendar
    if day_tasks:
        text += "\n\n### 📌 تسک‌های این ماه\n\n"
        text += "| روز | عنوان تسک‌ها |\n|---|---|\n"

        for day in sorted(day_tasks.keys()):
            titles = " — ".join(day_tasks[day])
            text += f"| {day} | {titles} |\n"
    else:
        text += "\n\n_در این ماه تسکی با مهلت ثبت‌شده وجود ندارد._"

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"markdown": text},
        },
    )


async def reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route report_* callbacks."""

    query = update.callback_query
    data = query.data

    if data == "report_all":
        await report_all_tasks(update, context)
    elif data == "report_priority":
        await report_by_priority(update, context)
    elif data == "report_status":
        await report_by_status(update, context)
    elif data == "report_calendar":
        await report_calendar(update, context)
    elif data == "report_back":
        await query.answer()
        await query.message.reply_text(
            "منوی اصلی:",
            reply_markup=__import__("handlers.menu", fromlist=["main_menu"]).main_menu()
        )
