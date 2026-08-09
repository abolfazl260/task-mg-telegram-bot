"""Runtime display/report adapters for the per-user calendar setting.

Storage and task queries remain Gregorian ISO. This module is intentionally
kept separate so existing handlers can be adapted without changing storage.
"""

from collections import defaultdict
from datetime import datetime, timedelta
import calendar

import jdatetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.date_service import (
    calendar_month_bounds,
    format_date,
    format_datetime,
    get_user_date_format_for_display,
    selected_calendar_today,
    user_today,
)
from services.task_service import get_all_user_tasks, get_task_by_id, get_task_comments


_DAY_NAMES = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def _rich(context, chat_id, text):
    return context.bot._post(
        "sendRichMessage",
        data={"chat_id": chat_id, "rich_message": {"markdown": text}},
    )


def _parse_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except Exception:
            pass
    return None


def _display_day(user_id, value):
    return format_date(value, get_user_date_format_for_display(user_id))


def _month_label(user_id, year=None, month=None):
    fmt = get_user_date_format_for_display(user_id)
    if year is None or month is None:
        year, month, _ = selected_calendar_today(user_id)
    if fmt == "gregorian":
        return f"{year}/{month:02d}"
    return f"{jdatetime.date(year, month, 1).j_months_fa[month - 1]} {year}"


def _calendar_grid(start, end):
    cal = calendar.Calendar(firstweekday=5)
    return cal.monthdayscalendar(start.year, start.month)


def _selected_month_tasks(user_id, tasks):
    start, end = calendar_month_bounds(user_id)
    result = defaultdict(list)
    for task in tasks:
        d = _parse_date(task.get("deadline"))
        if d and start <= d <= end:
            result[d].append(task)
    return start, end, result


async def report_calendar(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    start, end, day_tasks = _selected_month_tasks(user_id, tasks)
    fmt = get_user_date_format_for_display(user_id)

    title = _month_label(user_id)
    cal = calendar.Calendar(firstweekday=5)
    weeks = cal.monthdayscalendar(start.year, start.month)
    text = f"# 📅 تقویم تسک‌ها — {title}\n\n"
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n|---|---|---|---|---|---|---|\n"

    for week in weeks:
        cells = []
        for day in week:
            if day == 0:
                cells.append(" ")
                continue
            d = start.replace(day=day)
            # For Jalali calendar, the Gregorian grid is still used internally;
            # displayed day number is converted to the selected calendar.
            display_day = d.day if fmt == "gregorian" else jdatetime.date.fromgregorian(date=d).day
            cell = f"**{display_day}**"
            if d in day_tasks:
                titles = day_tasks[d]
                lines = "<br>".join(t.get("title", "-") for t in titles[:2])
                if len(titles) > 2:
                    lines += f"<br>+{len(titles)-2} مورد"
                cell += f"<br>{lines}"
            cells.append(cell)
        text += "| " + " | ".join(cells) + " |\n"

    if day_tasks:
        text += "\n\n### 📌 تسک‌های این ماه\n\n| تاریخ | عنوان تسک‌ها |\n|---|---|\n"
        for d in sorted(day_tasks):
            text += f"| {_display_day(user_id, d)} | {' — '.join(t.get('title', '-') for t in day_tasks[d])} |\n"
    else:
        text += "\n\n_در این ماه تسکی با مهلت ثبت‌شده وجود ندارد._"
    await _rich(context, update.effective_chat.id, text)


async def report_week(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    today = user_today(user_id)
    text = "# 📆 تقویم ۷ روز آینده\n\n"
    for i in range(7):
        d = today + timedelta(days=i)
        items = [t for t in tasks if _parse_date(t.get("deadline")) == d]
        label = "امروز" if i == 0 else ("فردا" if i == 1 else _DAY_NAMES[d.weekday()])
        text += f"## {label} — {_display_day(user_id, d)}\n\n"
        if not items:
            text += "_تسکی ندارید_\n\n"
            continue
        text += "| # | عنوان | اولویت | وضعیت |\n|---|---|---|---|\n"
        for idx, task in enumerate(items, 1):
            p = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(task.get("priority"), "🟢")
            s = {"pending": "⏳", "in_progress": "🚀", "done": "✅", "cancelled": "❌"}.get(task.get("status"), "⏳")
            text += f"| {idx} | {task.get('title','-')} | {p} | {s} |\n"
        text += "\n"
    await _rich(context, update.effective_chat.id, text)


async def report_today(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    today = user_today(user_id)
    tasks = [t for t in get_all_user_tasks(user_id) if _parse_date(t.get("deadline")) == today and t.get("status") in ("pending", "in_progress")]
    tasks.sort(key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t.get("priority"), 3))
    if not tasks:
        await query.message.reply_text("☀️ برای امروز تسک فعالی با مهلت امروز ندارید.")
        return
    text = f"# ☀️ برنامه امروز\n\nتاریخ: **{_display_day(user_id, today)}**\n\n| # | عنوان | اولویت | وضعیت | دسته |\n|---|---|---|---|---|\n"
    for i, task in enumerate(tasks, 1):
        p = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(task.get("priority"), "🟢")
        s = {"pending": "⏳", "in_progress": "🚀", "done": "✅", "cancelled": "❌"}.get(task.get("status"), "⏳")
        text += f"| {i} | {task.get('title','-')} | {p} | {s} | {task.get('category') or '—'} |\n"
    text += f"\n\n📌 **{len(tasks)}** تسک برای امروز"
    await _rich(context, update.effective_chat.id, text)


async def report_heatmap(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    start, end, day_tasks = _selected_month_tasks(user_id, tasks)
    counts = {d: len(items) for d, items in day_tasks.items()}
    max_c = max(counts.values(), default=0)

    def intensity(n):
        if n <= 0 or max_c <= 0:
            return "⬜"
        ratio = n / max_c
        return "🟩" if ratio <= .25 else "🟨" if ratio <= .5 else "🟧" if ratio <= .75 else "🟥"

    fmt = get_user_date_format_for_display(user_id)
    title = _month_label(user_id)
    weeks = calendar.Calendar(firstweekday=5).monthdayscalendar(start.year, start.month)
    text = f"# 🌡 هیت‌مپ ماهانه — {title}\n\n"
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n| :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    for week in weeks:
        cells = []
        for day in week:
            if not day:
                cells.append("·")
                continue
            d = start.replace(day=day)
            n = counts.get(d, 0)
            display_day = d.day if fmt == "gregorian" else jdatetime.date.fromgregorian(date=d).day
            cells.append(f"{intensity(n)}<br>**{display_day}**<br>({n})" if n else f"⬜<br>**{display_day}**")
        text += "| " + " | ".join(cells) + " |\n"
    text += "\n\n📌 مبنای شمارش: مهلت ذخیره‌شده به‌صورت Gregorian؛ مرز ماه بر اساس تقویم انتخابی کاربر است."
    await _rich(context, update.effective_chat.id, text)


async def report_heatmap_week(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    today = user_today(user_id)
    tasks = get_all_user_tasks(user_id)
    text = "# 🔥 هیت‌مپ هفته (۷ روز آینده)\n\n| روز | تاریخ | تراکم | تعداد |\n|---|---|---|---|\n"
    counts = {}
    for i in range(7):
        d = today + timedelta(days=i)
        n = sum(1 for t in tasks if _parse_date(t.get("deadline")) == d)
        counts[d] = n
        label = "امروز" if i == 0 else ("فردا" if i == 1 else _DAY_NAMES[d.weekday()])
        text += f"| {label} | {_display_day(user_id, d)} | {'🟥' if n >= 4 else '🟧' if n == 3 else '🟨' if n == 2 else '🟩' if n == 1 else '⬜'} | {n} |\n"
    await _rich(context, update.effective_chat.id, text)


def _calendar_months(user_id, count=3):
    fmt = get_user_date_format_for_display(user_id)
    y, m, _ = selected_calendar_today(user_id)
    months = []
    for _ in range(count):
        months.append((y, m))
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
    return list(reversed(months)), fmt


def _bounds_for_calendar_month(user_id, year, month, fmt):
    if fmt == "gregorian":
        start = datetime(year, month, 1).date()
        if month == 12:
            end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end = datetime(year, month + 1, 1).date() - timedelta(days=1)
        return start, end
    start = jdatetime.date(year, month, 1).togregorian()
    next_start = jdatetime.date(year + 1, 1, 1).togregorian() if month == 12 else jdatetime.date(year, month + 1, 1).togregorian()
    return start, next_start - timedelta(days=1)


async def report_compare_months(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    months, fmt = _calendar_months(user_id)
    stats = []
    for y, m in months:
        start, end = _bounds_for_calendar_month(user_id, y, m, fmt)
        created = done = in_progress = 0
        for t in tasks:
            c = _parse_datetime(t.get("created_at"))
            completed = _parse_datetime(t.get("completed_at"))
            if c and start <= c.date() <= end:
                created += 1
            if t.get("status") == "done" and (completed or c) and start <= (completed or c).date() <= end:
                done += 1
            if t.get("status") == "in_progress" and c and start <= c.date() <= end:
                in_progress += 1
        stats.append({"y": y, "m": m, "created": created, "done": done, "in_progress": in_progress})

    labels = [_month_label(user_id, s["y"], s["m"]) for s in stats]
    text = "# 📊 مقایسه سه‌ماهه\n\n"
    text += "| شاخص | " + " | ".join(labels) + " |\n|---|" + "---|" * len(stats) + "\n"
    for key, label in (("created", "ایجادشده"), ("in_progress", "در حال انجام"), ("done", "انجام‌شده")):
        text += f"| {label} | " + " | ".join(str(s[key]) for s in stats) + " |\n"
    await _rich(context, update.effective_chat.id, text)


def format_task_card(task: dict, user_id: int | None = None) -> str:
    """Calendar-aware replacement for the task card; internal values are untouched."""
    if user_id is None:
        user_id = int(task.get("user_id") or 0) if str(task.get("user_id") or "").isdigit() else 0
    fmt = get_user_date_format_for_display(user_id)
    title = task.get("title", "-")
    task_id = task.get("id", "")
    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(task.get("priority"), task.get("priority", "-"))
    status = {"pending": "⏳ در انتظار", "in_progress": "🚀 در حال انجام", "done": "✅ انجام شده", "cancelled": "❌ لغو شده"}.get(task.get("status"), task.get("status", "-"))
    deadline = task.get("deadline")
    created = task.get("created_at")
    remaining = "—"
    if deadline:
        d = _parse_date(deadline)
        if d:
            diff = (d - user_today(user_id)).days
            remaining = "⏰ امروز" if diff == 0 else (f"🔻 {abs(diff)} روز گذشته" if diff < 0 else f"🕒 {diff} روز مانده")
    deadline_display = format_date(deadline, fmt) if deadline else "بدون ددلاین"
    created_display = format_datetime(created, fmt) if created else "—"
    assignee = task.get("assignee_name") or "❌ تعیین نشده"
    comments_count = len(get_task_comments(task_id)) if task_id else 0
    return (
        f"**{title}**\n\n🆔 `{task_id}`\n"
        f"🎯 اولویت: {priority}\n📌 وضعیت: {status}\n👤 مسئول: {assignee}\n"
        f"📅 مهلت: {deadline_display}\n⏳ باقی‌مانده: {remaining}\n"
        f"📂 دسته: {task.get('category') or '—'}\n🏷 تگ: {task.get('tags') or '—'}\n"
        f"📄 توضیح: {task.get('description') or '—'}\n🕐 ثبت: {created_display}\n💬 کامنت‌ها: {comments_count}"
    )


def build_full_report(tasks, user_id: int | None = None) -> str:
    fmt = get_user_date_format_for_display(user_id or 0)
    text = "# 📊 گزارش پیگیری اقدامات\n\n| # | موضوع | مسئول | دسته | تگ | اولویت | مهلت | زمان | وضعیت | توضیح |\n|---|---|---|---|---|---|---|---|---|---|\n"
    for index, task in enumerate(tasks, 1):
        deadline = task.get("deadline")
        d = _parse_date(deadline)
        diff = (d - user_today(user_id or 0)).days if d else None
        remaining = "—" if diff is None else (f"🔻{abs(diff)}" if diff < 0 else "⏰" if diff == 0 else f"🕒{diff}")
        p = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(task.get("priority"), "🟢")
        s = {"pending": "⏳", "in_progress": "🚀", "done": "✅", "cancelled": "❌"}.get(task.get("status"), "-")
        text += f"| {index} | {task.get('title','-')} | {task.get('assignee_name') or 'بدون مسئول'} | {task.get('category') or '-'} | {task.get('tags') or '-'} | {p} | {format_date(deadline, fmt) if d else '-'} | {remaining} | {s} | {(task.get('description') or '-')[:40]} |\n"
    return text
