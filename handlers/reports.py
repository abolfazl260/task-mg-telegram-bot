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


def _parse_created(created_at: str):
    try:
        return datetime.strptime(created_at.strip()[:16], "%Y-%m-%d %H:%M")
    except Exception:
        try:
            return datetime.strptime(created_at.strip()[:10], "%Y-%m-%d")
        except Exception:
            return None


def reports_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 کل تسک‌ها", callback_data="report_all")],
        [InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="report_priority")],
        [InlineKeyboardButton("📊 وضعیت تسک‌ها", callback_data="report_status")],
        [InlineKeyboardButton("🔥 کارهای گیرکرده (+۳ روز)", callback_data="report_stuck")],
        [InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags")],
        [InlineKeyboardButton("📅 تقویم ماه جاری", callback_data="report_calendar")],
        [InlineKeyboardButton("📆 تقویم ۷ روزه", callback_data="report_week")],
        [InlineKeyboardButton("🌡 هیت‌مپ ماهانه", callback_data="report_heatmap")],
        [InlineKeyboardButton("📈 روند هفتگی", callback_data="report_trend")],
        [InlineKeyboardButton("☀️ برنامه امروز", callback_data="report_today")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="report_back")],
    ])


async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

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


async def _send_rich(context, chat_id, markdown_text):
    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": chat_id,
            "rich_message": {"markdown": markdown_text},
        },
    )


async def report_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)

    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return

    tasks = sorted(tasks, key=lambda t: t.get("deadline") or "9999-99-99")

    table = "# 📋 گزارش کل تسک‌ها\n\n"
    table += "| # | عنوان | اولویت | وضعیت | مهلت | دسته‌بندی |\n"
    table += "|---|---|---|---|---|---|\n"

    for i, task in enumerate(tasks, start=1):
        table += (
            f"| {i} "
            f"| {task.get('title', '-')} "
            f"| {_priority_emoji(task.get('priority'))} "
            f"| {_status_label(task.get('status'))} "
            f"| {task.get('deadline') or '—'} "
            f"| {task.get('category') or '—'} |\n"
        )

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
                f"| {task.get('deadline') or '—'} |\n"
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
        "# 📊 وضعیت تسک‌ها\n\n"
        f"| وضعیت | تعداد | درصد |\n"
        f"|---|---|---|\n"
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
        await query.message.reply_text(
            "🎉 هیچ تسک گیرکرده‌ای (در حال انجام بیش از ۳ روز) ندارید."
        )
        return

    text = "# 🔥 کارهای گیرکرده\n\n"
    text += "تسک‌هایی که بیش از **۳ روز** در وضعیت «در حال انجام» مانده‌اند:\n\n"
    text += "| # | عنوان | روزهای گیرکرده | اولویت | مهلت |\n|---|---|---|---|---|\n"

    for i, (task, days) in enumerate(stuck, start=1):
        text += (
            f"| {i} "
            f"| {task.get('title', '-')} "
            f"| {days} روز "
            f"| {_priority_emoji(task.get('priority'))} "
            f"| {task.get('deadline') or '—'} |\n"
        )

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
        text += f"## 📁 {cat} — {len(items)} تسک\n\n"
        text += "| # | عنوان | اولویت | وضعیت | مهلت |\n|---|---|---|---|---|\n"

        for i, task in enumerate(items, start=1):
            text += (
                f"| {i} "
                f"| {task.get('title', '-')} "
                f"| {_priority_emoji(task.get('priority'))} "
                f"| {_status_label(task.get('status'))} "
                f"| {task.get('deadline') or '—'} |\n"
            )

        text += "\n"

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
        text += f"## #{tag} — {len(items)} تسک\n\n"
        text += "| # | عنوان | اولویت | وضعیت |\n|---|---|---|---|\n"

        for i, task in enumerate(items, start=1):
            text += (
                f"| {i} "
                f"| {task.get('title', '-')} "
                f"| {_priority_emoji(task.get('priority'))} "
                f"| {_status_label(task.get('status'))} |\n"
            )

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
                shown = titles[:2]
                extra = len(titles) - 2
                lines = "<br>".join(shown)
                if extra > 0:
                    lines += f"<br>+{extra} مورد"
                cell = f"**{day}**<br>{lines}"

            cells.append(cell)

        text += "| " + " | ".join(cells) + " |\n"

    if day_tasks:
        text += "\n\n### 📌 تسک‌های این ماه\n\n"
        text += "| روز | عنوان تسک‌ها |\n|---|---|\n"
        for day in sorted(day_tasks.keys()):
            titles = " — ".join(day_tasks[day])
            text += f"| {day} | {titles} |\n"
    else:
        text += "\n\n_در این ماه تسکی با مهلت ثبت‌شده وجود ندارد._"

    await _send_rich(context, update.effective_chat.id, text)


async def report_week(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()

    day_names_fa = [
        "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه",
        "جمعه", "شنبه", "یکشنبه"
    ]

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
            j = jdatetime.date.fromgregorian(date=d)
            j_str = j.strftime("%Y/%m/%d")
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
            text += (
                f"| {idx} "
                f"| {task.get('title', '-')} "
                f"| {_priority_emoji(task.get('priority'))} "
                f"| {_status_label(task.get('status'))} |\n"
            )

        text += "\n"

    await _send_rich(context, update.effective_chat.id, text)


async def report_heatmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monthly heatmap: full calendar grid, then intensity emoji in each cell."""

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

    # Build full month grid (Sat-first for Iran)
    cal = calendar.Calendar(firstweekday=5)
    weeks = cal.monthdayscalendar(year, month)

    text = f"# 🌡 هیت‌مپ ماهانه — {title_month}\n\n"
    text += "تراکم تسک‌ها بر اساس مهلت در هر روز ماه:\n\n"

    # Header row
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n"
    text += "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"

    for week in weeks:
        cells = []
        for day in week:
            if day == 0:
                # empty cell outside the month
                cells.append("·")
            else:
                n = counts.get(day, 0)
                emoji = intensity(n)
                # day number + emoji on same visual cell
                if n > 0:
                    cells.append(f"{emoji}<br>**{day}**<br>({n})")
                else:
                    cells.append(f"{emoji}<br>**{day}**")
        text += "| " + " | ".join(cells) + " |\n"

    text += (
        "\n\n📌 **راهنما**\n\n"
        "| ایموجی | معنی |\n"
        "|---|---|\n"
        "| ⬜ | بدون تسک |\n"
        "| 🟩 | تراکم کم |\n"
        "| 🟨 | تراکم متوسط |\n"
        "| 🟧 | تراکم زیاد |\n"
        "| 🟥 | تراکم خیلی زیاد |\n"
    )

    if counts:
        text += f"\n📊 پرتراکم‌ترین روز: **{max(counts, key=counts.get)}** با {max_c} تسک"

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
    max_val = max(
        [created_counts[d] for d in days] + [done_counts[d] for d in days] + [1]
    )

    def bar(n):
        if n <= 0:
            return "░"
        filled = max(1, round(n / max_val * 8))
        return "█" * filled + "░" * (8 - filled)

    day_names = ["دش", "سه", "چه", "پن", "جم", "شن", "یک"]

    text = "# 📈 روند هفتگی (۷ روز اخیر)\n\n"
    text += "تعداد تسک **ایجادشده** در هر روز:\n\n"
    text += "```\n"

    for d in days:
        name = day_names[d.weekday()]
        n = created_counts[d]
        text += f"{name} {d.strftime('%m/%d')} | {bar(n)} {n}\n"

    text += "```\n\n"
    text += "تعداد تسک **انجام‌شده** (تقریبی):\n\n"
    text += "```\n"

    for d in days:
        name = day_names[d.weekday()]
        n = done_counts[d]
        text += f"{name} {d.strftime('%m/%d')} | {bar(n)} {n}\n"

    text += "```\n"

    await _send_rich(context, update.effective_chat.id, text)


async def report_today(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)
    today_str = date.today().isoformat()

    today_tasks = [
        t for t in tasks
        if (t.get("deadline") or "") == today_str
        and t.get("status") in ("pending", "in_progress")
    ]

    today_tasks = sorted(
        today_tasks,
        key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t.get("priority"), 3)
    )

    if not today_tasks:
        await query.message.reply_text(
            "☀️ برای امروز تسک فعالی با مهلت امروز ندارید."
        )
        return

    text = "# ☀️ برنامه امروز\n\n"
    text += f"تاریخ: **{today_str}**\n\n"
    text += "| # | عنوان | اولویت | وضعیت | دسته |\n|---|---|---|---|---|\n"

    for i, task in enumerate(today_tasks, start=1):
        text += (
            f"| {i} "
            f"| {task.get('title', '-')} "
            f"| {_priority_emoji(task.get('priority'))} "
            f"| {_status_label(task.get('status'))} "
            f"| {task.get('category') or '—'} |\n"
        )

    text += f"\n\n📌 **{len(today_tasks)}** تسک برای امروز"

    await _send_rich(context, update.effective_chat.id, text)


async def reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    data = query.data

    routes = {
        "report_all": report_all_tasks,
        "report_priority": report_by_priority,
        "report_status": report_by_status,
        "report_stuck": report_stuck,
        "report_category": report_by_category,
        "report_tags": report_by_tags,
        "report_calendar": report_calendar,
        "report_week": report_week,
        "report_heatmap": report_heatmap,
        "report_trend": report_trend,
        "report_today": report_today,
    }

    if data == "report_back":
        await query.answer()
        from handlers.menu import main_menu
        await query.message.reply_text(
            "منوی اصلی:",
            reply_markup=main_menu()
        )
        return

    handler = routes.get(data)
    if handler:
        await handler(update, context)
