"""Calendar-aware replacements for legacy reports that expose dates."""

from collections import defaultdict
from datetime import datetime, timedelta

from services.date_service import format_date, format_datetime, get_user_date_format_for_display, user_today
from services.task_service import get_all_user_tasks


def _d(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _p(task):
    return {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(task.get("priority"), "🟢")


def _s(task):
    return {"pending": "⏳", "in_progress": "🚀", "done": "✅", "cancelled": "❌"}.get(task.get("status"), "—")


async def report_all_tasks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = sorted(get_all_user_tasks(user_id), key=lambda t: t.get("deadline") or "9999-99-99")
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی ثبت نکرده‌اید.")
        return
    fmt = get_user_date_format_for_display(user_id)
    text = "# 📋 فهرست کل وظایف\n\n| # | عنوان | مسئول | اولویت | وضعیت | مهلت | دسته‌بندی |\n|---|---|---|---|---|---|---|\n"
    for i, task in enumerate(tasks, 1):
        d = _d(task.get("deadline"))
        deadline = format_date(d, fmt) if d else "—"
        text += f"| {i} | {task.get('title','-')} | {task.get('assignee_name') or 'بدون مسئول'} | {_p(task)} | {_s(task)} | {deadline} | {task.get('category') or '—'} |\n"
    text += f"\n📌 مجموع: **{len(tasks)}** تسک"
    await context.bot._post("sendRichMessage", data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}})


async def report_by_priority(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    fmt = get_user_date_format_for_display(user_id)
    groups = {"high": [], "medium": [], "low": []}
    for task in tasks:
        groups.setdefault(task.get("priority") or "low", []).append(task)
    text = "# 🎯 گزارش بر اساس اولویت\n\n"
    for key, label, emoji in (("high", "بالا", "🔴"), ("medium", "متوسط", "🟠"), ("low", "پایین", "🟢")):
        items = groups[key]
        text += f"## {emoji} اولویت {label} — {len(items)} تسک\n\n"
        text += "| # | عنوان | وضعیت | مهلت | دسته‌بندی |\n|---|---|---|---|---|\n"
        for i, task in enumerate(items, 1):
            d = _d(task.get("deadline"))
            text += f"| {i} | {task.get('title','-')} | {_s(task)} | {format_date(d, fmt) if d else '—'} | {task.get('category') or '—'} |\n"
        text += "\n"
    await context.bot._post("sendRichMessage", data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}})


async def report_stuck(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    now = user_today(user_id)
    stuck = []
    for task in get_all_user_tasks(user_id):
        if task.get("status") != "in_progress":
            continue
        try:
            created = datetime.strptime(str(task.get("created_at"))[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        days = (now - created).days
        if days >= 3:
            stuck.append((task, days))
    if not stuck:
        await query.message.reply_text("🎉 هیچ کار معطل‌مانده‌ای ندارید.")
        return
    fmt = get_user_date_format_for_display(user_id)
    text = "# 🔥 کارهای معطل‌مانده\n\n| # | عنوان | روزهای معطل‌مانده | مهلت |\n|---|---|---|---|\n"
    for i, (task, days) in enumerate(sorted(stuck, key=lambda x: x[1], reverse=True), 1):
        d = _d(task.get("deadline"))
        text += f"| {i} | {task.get('title','-')} | {days} روز | {format_date(d, fmt) if d else '—'} |\n"
    await context.bot._post("sendRichMessage", data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}})


async def report_trend(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    today = user_today(user_id)
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    created = defaultdict(int)
    done = defaultdict(int)
    for task in get_all_user_tasks(user_id):
        c = None
        try:
            c = datetime.strptime(str(task.get("created_at"))[:10], "%Y-%m-%d").date()
        except Exception:
            pass
        if c in days:
            created[c] += 1
        if task.get("status") == "done":
            completed = _d(task.get("completed_at")) or c
            if completed in days:
                done[completed] += 1
    fmt = get_user_date_format_for_display(user_id)
    text = "# 📈 روند هفتگی (۷ روز اخیر)\n\n| تاریخ | ایجادشده | انجام‌شده |\n|---|---:|---:|\n"
    for d in days:
        text += f"| {format_date(d, fmt)} | {created[d]} | {done[d]} |\n"
    await context.bot._post("sendRichMessage", data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}})
