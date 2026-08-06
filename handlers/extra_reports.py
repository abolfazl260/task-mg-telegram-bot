from datetime import datetime, date
from calendar import monthrange

from telegram import Update
from telegram.ext import ContextTypes

from services.task_service import get_all_user_tasks


def _parse_dt(s: str):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:16] if " " in s else s[:10], fmt)
        except Exception:
            continue
    return None


async def _send_rich(context, chat_id, markdown_text):
    await context.bot._post(
        "sendRichMessage",
        data={"chat_id": chat_id, "rich_message": {"markdown": markdown_text}},
    )


async def report_compare_months(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)
    today = date.today()

    this_y, this_m = today.year, today.month
    if this_m == 1:
        last_y, last_m = this_y - 1, 12
    else:
        last_y, last_m = this_y, this_m - 1

    def in_month(dt, y, m):
        return dt and dt.year == y and dt.month == m

    created_this = created_last = done_this = done_last = 0

    for t in tasks:
        created = _parse_dt(t.get("created_at", ""))
        completed = _parse_dt(t.get("completed_at", ""))

        if in_month(created, this_y, this_m):
            created_this += 1
        if in_month(created, last_y, last_m):
            created_last += 1
        if t.get("status") == "done" and in_month(completed or created, this_y, this_m):
            done_this += 1
        if t.get("status") == "done" and in_month(completed or created, last_y, last_m):
            done_last += 1

    def delta(a, b):
        if b == 0:
            return "—" if a == 0 else f"+{a}"
        diff = a - b
        pct = round(diff / b * 100)
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct}%"

    text = (
        "# 📊 مقایسه این ماه با ماه قبل\n\n"
        f"| شاخص | ماه قبل ({last_y}/{last_m}) | این ماه ({this_y}/{this_m}) | تغییر |\n"
        f"|---|---|---|---|\n"
        f"| ایجادشده | {created_last} | {created_this} | {delta(created_this, created_last)} |\n"
        f"| انجام‌شده | {done_last} | {done_this} | {delta(done_this, done_last)} |\n"
    )

    await _send_rich(context, update.effective_chat.id, text)


async def report_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    tasks = get_all_user_tasks(update.effective_user.id)

    if not tasks:
        await query.message.reply_text("هنوز تسکی ندارید.")
        return

    total = len(tasks)
    done = [t for t in tasks if t.get("status") == "done"]
    cancelled = [t for t in tasks if t.get("status") == "cancelled"]
    active = [t for t in tasks if t.get("status") in ("pending", "in_progress")]

    rate = round(len(done) / total * 100) if total else 0

    durations = []
    for t in done:
        c = _parse_dt(t.get("created_at", ""))
        f = _parse_dt(t.get("completed_at", "")) or c
        if c and f:
            durations.append(max(0, (f - c).total_seconds() / 86400))

    avg_days = round(sum(durations) / len(durations), 1) if durations else None

    text = (
        "# 📈 نرخ انجام و سرعت بستن تسک\n\n"
        f"| شاخص | مقدار |\n|---|---|\n"
        f"| کل تسک‌ها | {total} |\n"
        f"| انجام‌شده | {len(done)} |\n"
        f"| فعال | {len(active)} |\n"
        f"| لغو شده | {len(cancelled)} |\n"
        f"| نرخ انجام | **{rate}%** |\n"
        f"| میانگین زمان بستن | "
        + (f"**{avg_days} روز**" if avg_days is not None else "داده کافی نیست")
        + " |\n"
    )

    if durations:
        text += (
            f"\n📌 سریع‌ترین بستن: {round(min(durations), 1)} روز\n"
            f"📌 کندترین بستن: {round(max(durations), 1)} روز\n"
        )

    await _send_rich(context, update.effective_chat.id, text)
