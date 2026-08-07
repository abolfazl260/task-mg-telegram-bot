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
        [InlineKeyboardButton("📋 کل تسک‌ها", callback_data="report_all")],
        [InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="report_priority")],
        [InlineKeyboardButton("📊 وضعیت تسک‌ها", callback_data="report_status")],
        [InlineKeyboardButton("🔥 کارهای گیرکرده (+۳ روز)", callback_data="report_stuck")],
        [InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee")],
        [InlineKeyboardButton("🧩 کانبان مسئولین", callback_data="report_kanban")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags")],
        [InlineKeyboardButton("📅 تقویم ماه جاری", callback_data="report_calendar")],
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
    table = "# 📋 گزارش کل تسک‌ها\n\n| # | عنوان | مسئول | اولویت | وضعیت | مهلت | دسته‌بندی |\n|---|---|---|---|---|---|---|\n"
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
        await query.message.reply_text("🎉 هیچ تسک گیرکرده‌ای (در حال انجام بیش از ۳ روز) ندارید.")
        return
    text = "# 🔥 کارهای گیرکرده\n\nتسک‌هایی که بیش از **۳ روز** در وضعیت «در حال انجام» مانده‌اند:\n\n| # | عنوان | روزهای گیرکرده | اولویت | مهلت |\n|---|---|---|---|---|\n"
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
        items = sorted(groups[assignee], key=lambda t: (t.get("deadline") or "9999-99-99", t.get("title") or ""))
        done = sum(1 for task in items if task.get("status") == "done")
        text += f"### 👤 {assignee} — {len(items)} تسک — عملکرد: {_performance_label(done, len(items))} ({_pct(done, len(items))})\n\n"
        text += "| # | موضوع | دسته | تگ | اولویت | مهلت میلادی | مهلت شمسی | وضعیت | توضیح |\n|---|---|---|---|---|---|---|---|---|\n"
        for i, task in enumerate(items, start=1):
            desc = (task.get("description") or "—").replace("\n", " ")[:50]
            text += (
                f"| {i} | {task.get('title', '—')} | {task.get('category') or '—'} | {task.get('tags') or '—'} "
                f"| {_priority_emoji(task.get('priority'))} | {task.get('deadline') or '—'} | {_jalali_str(task.get('deadline') or '')} "
                f"| {_status_label(task.get('status'))} | {desc} |\n"
            )
        text += "\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_kanban_by_assignee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return

    groups = defaultdict(list)
    for task in tasks:
        groups[_assignee_label(task)].append(task)

    statuses = [("pending", "⏳ شروع‌نشده"), ("in_progress", "🚀 در حال انجام"), ("done", "✅ انجام‌شده"), ("cancelled", "❌ لغو/رد")]
    text = "# 🧩 Kanban Board بر اساس مسئولیت افراد\n\n"
    for assignee in sorted(groups.keys(), key=lambda a: (-len(groups[a]), a)):
        items = groups[assignee]
        done = sum(1 for task in items if task.get("status") == "done")
        text += f"## 👤 {assignee} — مجموع {len(items)} — عملکرد: {_performance_label(done, len(items))} ({_pct(done, len(items))})\n\n"
        text += "| شروع‌نشده | در حال انجام | انجام‌شده | لغو/رد |\n|---|---|---|---|\n"
        columns = []
        for status_key, _ in statuses:
            status_items = [task for task in items if task.get("status") == status_key]
            status_items = sorted(status_items, key=lambda t: (t.get("deadline") or "9999-99-99", t.get("title") or ""))
            cell = f"**{len(status_items)}** مورد"
            if status_items:
                lines = []
                for task in status_items[:6]:
                    lines.append(f"{_priority_emoji(task.get('priority'))} {task.get('title', '—')} ({task.get('deadline') or '—'})")
                if len(status_items) > 6:
                    lines.append(f"… و {len(status_items) - 6} مورد دیگر")
                cell += "<br>" + "<br>".join(lines)
            columns.append(cell)
        text += "| " + " | ".join(columns) + " |\n\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_by_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return
    groups = defaultdict(list)
    for task in tasks:
        raw = (task.get("tags") or "").strip()
        if not raw:
            groups["بدون تگ"].append(task)
            continue
        parts = [t.strip() for t in raw.replace(",", " ").split() if t.strip()]
        if not parts:
            groups["بدون تگ"].append(task)
        else:
            for tag in parts:
                groups[tag].append(task)
    text = "# 🏷 گزارش بر اساس تگ\n\n"
    for tag in sorted(groups.keys(), key=lambda t: (-len(groups[t]), t)):
        items = groups[tag]
        text += f"## #{tag} — {len(items)} تسک\n\n| # | عنوان | اولویت | وضعیت |\n|---|---|---|---|\n"
        for i, task in enumerate(items, start=1):
            text += f"| {i} | {task.get('title', '-')} | {_priority_emoji(task.get('priority'))} | {_status_label(task.get('status'))} |\n"
        text += "\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()
    year, month = today.year, today.month
    day_tasks = defaultdict(list)
    for task in tasks:
        deadline = task.get("deadline") or ""
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
            if d.year == year and d.month == month:
                day_tasks[d.day].append(task.get("title", "-"))
        except Exception:
            continue
    try:
        j_today = jdatetime.date.fromgregorian(date=today)
        title_month = f"{j_today.j_months_fa[j_today.month - 1]} {j_today.year}"
    except Exception:
        title_month = f"{year}/{month}"
    cal = calendar.Calendar(firstweekday=5)
    weeks = cal.monthdayscalendar(year, month)
    text = f"# 📅 تقویم تسک‌ها — {title_month}\n\n| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n|---|---|---|---|---|---|---|\n"
    for week in weeks:
        cells = []
        for day in week:
            if day == 0:
                cells.append(" ")
                continue
            cell = f"**{day}**"
            if day in day_tasks:
                titles = day_tasks[day]
                shown = titles[:2]
                extra = len(titles) - 2
                lines = "<br>".join(shown)
                if extra > 0:
                    lines += f"<br>+{extra} مورد"
                cell = f"**{day}**<br>{lines}"
            cells.append(cell)
        text += "| " + " | ".join(cells) + " |\n"
    if day_tasks:
        text += "\n\n### 📌 تسک‌های این ماه\n\n| روز | عنوان تسک‌ها |\n|---|---|\n"
        for day in sorted(day_tasks.keys()):
            text += f"| {day} | {' — '.join(day_tasks[day])} |\n"
    else:
        text += "\n\n_در این ماه تسکی با مهلت ثبت‌شده وجود ندارد._"
    await _send_rich(context, update.effective_chat.id, text)


async def report_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()
    day_names_fa = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
    day_tasks = defaultdict(list)
    for task in tasks:
        deadline = task.get("deadline") or ""
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
            delta = (d - today).days
            if 0 <= delta <= 6:
                day_tasks[d].append(task)
        except Exception:
            continue
    text = "# 📆 تقویم ۷ روز آینده\n\n"
    for i in range(7):
        d = today + timedelta(days=i)
        weekday = day_names_fa[d.weekday()]
        try:
            j_str = jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")
        except Exception:
            j_str = d.isoformat()
        label = "امروز" if i == 0 else ("فردا" if i == 1 else weekday)
        items = day_tasks.get(d, [])
        text += f"## {label} — {j_str}\n\n"
        if not items:
            text += "_تسکی ندارید_\n\n"
            continue
        text += "| # | عنوان | اولویت | وضعیت |\n|---|---|---|---|\n"
        for idx, task in enumerate(items, start=1):
            text += f"| {idx} | {task.get('title', '-')} | {_priority_emoji(task.get('priority'))} | {_status_label(task.get('status'))} |\n"
        text += "\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_heatmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()
    year, month = today.year, today.month
    counts = defaultdict(int)
    for task in tasks:
        deadline = task.get("deadline") or ""
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
            if d.year == year and d.month == month:
                counts[d.day] += 1
        except Exception:
            continue
    max_c = max(counts.values()) if counts else 0

    def intensity(n):
        if n <= 0:
            return "⬜"
        if max_c <= 0:
            return "⬜"
        ratio = n / max_c
        if ratio <= 0.25:
            return "🟩"
        if ratio <= 0.5:
            return "🟨"
        if ratio <= 0.75:
            return "🟧"
        return "🟥"

    try:
        j_today = jdatetime.date.fromgregorian(date=today)
        title_month = f"{j_today.j_months_fa[j_today.month - 1]} {j_today.year}"
    except Exception:
        title_month = f"{year}/{month}"
    cal = calendar.Calendar(firstweekday=5)
    weeks = cal.monthdayscalendar(year, month)
    text = f"# 🌡 هیت‌مپ ماهانه — {title_month}\n\nتراکم تسک‌ها بر اساس مهلت در هر روز ماه:\n\n"
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n| :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    for week in weeks:
        cells = []
        for day in week:
            if day == 0:
                cells.append("·")
            else:
                n = counts.get(day, 0)
                emoji = intensity(n)
                cells.append(f"{emoji}<br>**{day}**<br>({n})" if n else f"{emoji}<br>**{day}**")
        text += "| " + " | ".join(cells) + " |\n"
    text += "\n\n📌 **راهنما**\n\n| ایموجی | معنی |\n|---|---|\n| ⬜ | بدون تسک |\n| 🟩 | تراکم کم |\n| 🟨 | تراکم متوسط |\n| 🟧 | تراکم زیاد |\n| 🟥 | تراکم خیلی زیاد |\n"
    if counts:
        text += f"\n📊 پرتراکم‌ترین روز: **{max(counts, key=counts.get)}** با {max_c} تسک"
    await _send_rich(context, update.effective_chat.id, text)


async def report_heatmap_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Weekly heatmap: density of tasks by deadline for the next 7 days."""

    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()

    # counts for today .. today+6
    counts = {}
    titles_by_day = defaultdict(list)
    for i in range(7):
        d = today + timedelta(days=i)
        counts[d] = 0

    for task in tasks:
        deadline = task.get("deadline") or ""
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
        except Exception:
            continue
        if d in counts:
            counts[d] += 1
            titles_by_day[d].append(task.get("title", "-"))

    max_c = max(counts.values()) if counts else 0

    def intensity(n):
        if n <= 0:
            return "⬜"
        if max_c <= 0:
            return "⬜"
        ratio = n / max_c
        if ratio <= 0.25:
            return "🟩"
        if ratio <= 0.5:
            return "🟨"
        if ratio <= 0.75:
            return "🟧"
        return "🟥"

    day_names_fa = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]

    text = "# 🔥 هیت‌مپ هفته (۷ روز آینده)\n\nتراکم تسک‌ها بر اساس مهلت:\n\n"
    text += "| روز | تاریخ | شمسی | تراکم | تعداد |\n|---|---|---|---|---|\n"

    for i in range(7):
        d = today + timedelta(days=i)
        n = counts[d]
        emoji = intensity(n)
        label = "امروز" if i == 0 else ("فردا" if i == 1 else day_names_fa[d.weekday()])
        try:
            j_str = jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")
        except Exception:
            j_str = "—"
        bar = emoji * min(n, 5) if n else "⬜"
        text += f"| **{label}** | {d.isoformat()} | {j_str} | {bar} | {n} |\n"

    text += "\n\n📌 **راهنما**\n\n| ایموجی | معنی |\n|---|---|\n| ⬜ | بدون تسک |\n| 🟩 | تراکم کم |\n| 🟨 | تراکم متوسط |\n| 🟧 | تراکم زیاد |\n| 🟥 | تراکم خیلی زیاد |\n"

    # detail of days that have tasks
    days_with = [d for d in sorted(counts.keys()) if counts[d] > 0]
    if days_with:
        text += "\n### 📌 جزئیات روزها\n\n"
        for d in days_with:
            try:
                j_str = jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")
            except Exception:
                j_str = d.isoformat()
            label = "امروز" if d == today else ("فردا" if d == today + timedelta(days=1) else day_names_fa[d.weekday()])
            text += f"**{label} ({j_str})** — {counts[d]} تسک:\n"
            for t in titles_by_day[d][:6]:
                text += f"• {t}\n"
            if len(titles_by_day[d]) > 6:
                text += f"• ... و {len(titles_by_day[d]) - 6} مورد دیگر\n"
            text += "\n"
    else:
        text += "\n_در ۷ روز آینده تسکی با مهلت ثبت‌شده ندارید._\n"

    if max_c > 0:
        busiest = max(counts, key=counts.get)
        try:
            j_busy = jdatetime.date.fromgregorian(date=busiest).strftime("%Y/%m/%d")
        except Exception:
            j_busy = busiest.isoformat()
        text += f"\n📊 پرتراکم‌ترین روز: **{j_busy}** با {max_c} تسک"

    await _send_rich(context, update.effective_chat.id, text)


async def report_trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()
    created_counts = defaultdict(int)
    done_counts = defaultdict(int)
    for task in tasks:
        created = _parse_created(task.get("created_at", ""))
        if created:
            d = created.date()
            if 0 <= (today - d).days <= 6:
                created_counts[d] += 1
        if task.get("status") == "done" and created:
            d = created.date()
            if 0 <= (today - d).days <= 6:
                done_counts[d] += 1
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    max_val = max([created_counts[d] for d in days] + [done_counts[d] for d in days] + [1])

    def bar(n):
        if n <= 0:
            return "░"
        filled = max(1, round(n / max_val * 8))
        return "█" * filled + "░" * (8 - filled)

    day_names = ["دش", "سه", "چه", "پن", "جم", "شن", "یک"]
    text = "# 📈 روند هفتگی (۷ روز اخیر)\n\nتعداد تسک **ایجادشده** در هر روز:\n\n```\n"
    for d in days:
        text += f"{day_names[d.weekday()]} {d.strftime('%m/%d')} | {bar(created_counts[d])} {created_counts[d]}\n"
    text += "```\n\nتعداد تسک **انجام‌شده** (تقریبی):\n\n```\n"
    for d in days:
        text += f"{day_names[d.weekday()]} {d.strftime('%m/%d')} | {bar(done_counts[d])} {done_counts[d]}\n"
    text += "```\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = get_all_user_tasks(update.effective_user.id)
    today_str = date.today().isoformat()
    today_tasks = [t for t in tasks if (t.get("deadline") or "") == today_str and t.get("status") in ("pending", "in_progress")]
    today_tasks = sorted(today_tasks, key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t.get("priority"), 3))
    if not today_tasks:
        await query.message.reply_text("☀️ برای امروز تسک فعالی با مهلت امروز ندارید.")
        return
    text = f"# ☀️ برنامه امروز\n\nتاریخ: **{today_str}**\n\n| # | عنوان | اولویت | وضعیت | دسته |\n|---|---|---|---|---|\n"
    for i, task in enumerate(today_tasks, start=1):
        text += f"| {i} | {task.get('title', '-')} | {_priority_emoji(task.get('priority'))} | {_status_label(task.get('status'))} | {task.get('category') or '—'} |\n"
    text += f"\n\n📌 **{len(today_tasks)}** تسک برای امروز"
    await _send_rich(context, update.effective_chat.id, text)


async def reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    from handlers.extra_reports import report_compare_months, report_performance, report_progress_bar
    routes = {
        "report_all": report_all_tasks,
        "report_priority": report_by_priority,
        "report_status": report_by_status,
        "report_stuck": report_stuck,
        "report_category": report_by_category,
        "report_assignee": report_by_assignee,
        "report_kanban": report_kanban_by_assignee,
        "report_tags": report_by_tags,
        "report_calendar": report_calendar,
        "report_week": report_week,
        "report_heatmap": report_heatmap,
        "report_heatmap_week": report_heatmap_week,
        "report_trend": report_trend,
        "report_today": report_today,
        "report_compare": report_compare_months,
        "report_perf": report_performance,
        "report_progress_bar": report_progress_bar,
    }
    if data == "report_back":
        await query.answer()
        from handlers.menu import main_menu
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu())
        return
    handler = routes.get(data)
    if handler:
        await handler(update, context)
