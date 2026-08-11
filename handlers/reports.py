from datetime import datetime, date, timedelta
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


def _pct(n, total):
    if total == 0:
        return "0%"
    return f"{round(n / total * 100)}%"


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


def _performance_label(done, total):
    if total == 0:
        return "—"
    rate = done / total
    if rate >= 0.8:
        return "عالی 🟢"
    if rate >= 0.5:
        return "خوب 🟡"
    if rate >= 0.25:
        return "نیازمند پیگیری 🟠"
    return "بحرانی 🔴"


def _parse_created(created_at: str):
    try:
        return datetime.strptime(created_at.strip()[:16], "%Y-%m-%d %H:%M")
    except Exception:
        try:
            return datetime.strptime(created_at.strip()[:10], "%Y-%m-%d")
        except Exception:
            return None


def _jalali_str(deadline: str) -> str:
    if not deadline:
        return "—"
    try:
        d = datetime.strptime(deadline, "%Y-%m-%d").date()
        return jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")
    except Exception:
        return "—"


def reports_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 فهرست کل وظایف", callback_data="report_all")],
        [InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="report_priority")],
        [InlineKeyboardButton("📊 وضعیت تسک‌ها", callback_data="report_status")],
        [InlineKeyboardButton("🔥 کارهای معطل‌مانده (+۳ روز)", callback_data="report_stuck")],
        [InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee")],
        [InlineKeyboardButton("🧩 برد کانبان", callback_data="report_kanban")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags")],
        [InlineKeyboardButton("📅 تقویم ماه جاری", callback_data="report_calendar")],
        [InlineKeyboardButton("📄 خروجی PDF تقویم ماهانه", callback_data="report_calendar_pdf")],
        [InlineKeyboardButton("📆 تقویم ۷ روزه", callback_data="report_week")],
        [InlineKeyboardButton("🌡 هیت‌مپ ماهانه", callback_data="report_heatmap")],
        [InlineKeyboardButton("🔥 هیت‌مپ هفته", callback_data="report_heatmap_week")],
        [InlineKeyboardButton("📈 روند هفتگی", callback_data="report_trend")],
        [InlineKeyboardButton("☀️ برنامه امروز", callback_data="report_today")],
        [InlineKeyboardButton("📊 مقایسه سه‌ماهه", callback_data="report_compare")],
        [InlineKeyboardButton("📈 نرخ انجام / میانگین زمان", callback_data="report_perf")],
        [InlineKeyboardButton("📊 نمودار پیشرفت", callback_data="report_progress_bar")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="report_back")],
    ])


async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "# 📊 بخش گزارشات\n\nیکی از گزینه‌های زیر را انتخاب کنید:"
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(text, reply_markup=reports_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reports_menu_keyboard(), parse_mode="Markdown")


async def _send_rich(context, chat_id, markdown_text):
    await context.bot._post("sendRichMessage", data={"chat_id": chat_id, "rich_message": {"markdown": markdown_text}})


async def report_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return
    tasks = sorted(tasks, key=lambda t: t.get("deadline") or "9999-99-99")
    table = "# 📋 فهرست کل وظایف\n\n| # | عنوان | مسئول | اولویت | وضعیت | مهلت | دسته‌بندی |\n|---|---|---|---|---|---|---|\n"
    for i, task in enumerate(tasks, start=1):
        table += f"| {i} | {task.get('title', '-')} | {_assignee_label(task)} | {_priority_emoji(task.get('priority'))} | {_status_label(task.get('status'))} | {task.get('deadline') or '—'} | {task.get('category') or '—'} |\n"
    table += f"\n\n📌 مجموع: **{len(tasks)}** تسک"
    await _send_rich(context, update.effective_chat.id, table)


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
        if p in groups:
            groups[p].append(task)
        else:
            groups["low"].append(task)
    text = "# 🎯 گزارش بر اساس اولویت\n\n"
    for key, label, emoji in [("high", "بالا", "🔴"), ("medium", "متوسط", "🟠"), ("low", "پایین", "🟢")]:
        items = groups[key]
        text += f"## {emoji} اولویت {label} — {len(items)} تسک\n\n"
        if not items:
            text += "_موردی نیست_\n\n"
            continue
        text += "| # | عنوان | وضعیت | مهلت (میلادی) | مهلت (شمسی) | دسته‌بندی |\n|---|---|---|---|---|---|\n"
        for i, task in enumerate(items, start=1):
            deadline = task.get("deadline") or "—"
            jalali = _jalali_str(task.get("deadline") or "")
            cat = task.get("category") or "—"
            text += (
                f"| {i} | {task.get('title', '-')} | {_status_label(task.get('status'))} "
                f"| {deadline} | {jalali} | {cat} |\n"
            )
        text += "\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return
    counts = {"pending": 0, "in_progress": 0, "done": 0, "cancelled": 0}
    for task in tasks:
        s = task.get("status", "pending")
        if s in counts:
            counts[s] += 1
    total = len(tasks)
    text = (
        "# 📊 وضعیت تسک‌ها\n\n| وضعیت | تعداد | درصد |\n|---|---|---|\n"
        f"| ⏳ شروع‌نشده | {counts['pending']} | {_pct(counts['pending'], total)} |\n"
        f"| 🚀 در حال انجام | {counts['in_progress']} | {_pct(counts['in_progress'], total)} |\n"
        f"| ✅ انجام‌شده | {counts['done']} | {_pct(counts['done'], total)} |\n"
        f"| ❌ رد / لغو شده | {counts['cancelled']} | {_pct(counts['cancelled'], total)} |\n"
        f"\n📌 **مجموع کل:** {total} تسک"
    )
    await _send_rich(context, update.effective_chat.id, text)


async def report_stuck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    now = datetime.now()
    stuck = []
    for task in tasks:
        if task.get("status") != "in_progress":
            continue
        created = _parse_created(task.get("created_at", ""))
        if not created:
            continue
        days = (now - created).days
        if days >= 3:
            stuck.append((task, days))
    stuck.sort(key=lambda x: x[1], reverse=True)
    if not stuck:
        await query.message.reply_text("🎉 هیچ کار معطل‌مانده‌ای (در حال انجام بیش از ۳ روز) ندارید.")
        return
    text = "# 🔥 کارهای معطل‌مانده\n\nتسک‌هایی که بیش از **۳ روز** در وضعیت «در حال انجام» مانده‌اند:\n\n| # | عنوان | روزهای معطل‌مانده | اولویت | مهلت |\n|---|---|---|---|---|\n"
    for i, (task, days) in enumerate(stuck, start=1):
        text += f"| {i} | {task.get('title', '-')} | {days} روز | {_priority_emoji(task.get('priority'))} | {task.get('deadline') or '—'} |\n"
    text += f"\n\n📌 تعداد: **{len(stuck)}** تسک"
    await _send_rich(context, update.effective_chat.id, text)


async def report_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return
    groups = defaultdict(list)
    for task in tasks:
        cat = (task.get("category") or "").strip() or "بدون دسته‌بندی"
        groups[cat].append(task)
    text = "# 📂 گزارش بر اساس دسته‌بندی\n\n"
    for cat in sorted(groups.keys(), key=lambda c: (-len(groups[c]), c)):
        items = groups[cat]
        text += f"## 📁 {cat} — {len(items)} تسک\n\n| # | عنوان | اولویت | وضعیت | مهلت |\n|---|---|---|---|---|\n"
        for i, task in enumerate(items, start=1):
            text += f"| {i} | {task.get('title', '-')} | {_priority_emoji(task.get('priority'))} | {_status_label(task.get('status'))} | {task.get('deadline') or '—'} |\n"
        text += "\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_by_assignee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return

    groups = defaultdict(list)
    for task in tasks:
        groups[_assignee_label(task)].append(task)

    total = len(tasks)
    text = "# 👤 گزارش اقدامات بر اساس مسئول\n\n"
    text += "## 📊 خلاصه عملکرد مسئولین\n\n| مسئول | مجموع | شروع‌نشده | در حال انجام | انجام‌شده | لغو | نرخ انجام | عملکرد |\n|---|---:|---:|---:|---:|---:|---:|---|\n"
    for assignee in sorted(groups.keys(), key=lambda a: (-len(groups[a]), a)):
        items = groups[assignee]
        counts = defaultdict(int)
        for task in items:
            counts[task.get("status", "pending")] += 1
        done = counts["done"]
        text += (
            f"| {assignee} | {len(items)} | {counts['pending']} | {counts['in_progress']} "
            f"| {done} | {counts['cancelled']} | {_pct(done, len(items))} "
            f"| {_performance_label(done, len(items))} |\n"
        )

    text += f"\n📌 **مجموع کل اقدامات:** {total} تسک\n\n"
    text += "## 📋 جزئیات کامل به تفکیک مسئول\n\n"
    for assignee in sorted(groups.keys(), key=lambda a: (-len(groups[a]), a)):
        items = groups[assignee]
        text += f"### 👤 {assignee} — {len(items)} تسک\n\n"
        text += "| # | عنوان | وضعیت | اولویت | مهلت | دسته‌بندی |\n|---|---|---|---|---|---|\n"
        for i, task in enumerate(items, start=1):
            text += f"| {i} | {task.get('title', '-')} | {_status_label(task.get('status'))} | {_priority_emoji(task.get('priority'))} | {task.get('deadline') or '—'} | {task.get('category') or '—'} |\n"
        text += "\n"
    await _send_rich(context, update.effective_chat.id, text)
