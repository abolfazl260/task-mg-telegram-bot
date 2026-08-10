import asyncio
from datetime import datetime, date

from telegram import Update
from telegram.ext import ContextTypes

from services.task_service import get_all_user_tasks


async def _db_call(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


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
    await context.bot._post("sendRichMessage", data={"chat_id": chat_id, "rich_message": {"markdown": markdown_text}})


def _month_label(y, m):
    return f"{y}/{m:02d}"


def _prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


async def report_compare_months(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = await _db_call(get_all_user_tasks, update.effective_user.id)
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(3):
        months.append((y, m))
        y, m = _prev_month(y, m)
    months.reverse()

    def in_month(dt, yy, mm):
        return dt and dt.year == yy and dt.month == mm

    stats = []
    for my, mm in months:
        created = done = in_progress = 0
        for t in tasks:
            c = _parse_dt(t.get("created_at", ""))
            completed = _parse_dt(t.get("completed_at", ""))
            if in_month(c, my, mm): created += 1
            if t.get("status") == "done" and in_month(completed or c, my, mm): done += 1
            if t.get("status") == "in_progress" and in_month(c, my, mm): in_progress += 1
        stats.append({"y": my, "m": mm, "created": created, "done": done, "in_progress": in_progress})

    text = "# 📊 مقایسه سه‌ماهه\n\n"
    text += "| شاخص | " + " | ".join(_month_label(s["y"], s["m"]) for s in stats) + " |\n|---|" + "---|" * len(stats) + "\n"
    text += "| ایجادشده | " + " | ".join(str(s["created"]) for s in stats) + " |\n"
    text += "| در حال انجام | " + " | ".join(str(s["in_progress"]) for s in stats) + " |\n"
    text += "| انجام‌شده | " + " | ".join(str(s["done"]) for s in stats) + " |\n"
    if len(stats) >= 2:
        last, prev = stats[-1], stats[-2]
        def delta(a, b):
            if b == 0: return "—" if a == 0 else f"+{a}"
            pct = round((a - b) / b * 100)
            return f"{'+' if pct > 0 else ''}{pct}%"
        text += f"\n📌 نسبت به ماه قبل:\n• ایجاد: {delta(last['created'], prev['created'])}\n• در حال انجام: {delta(last['in_progress'], prev['in_progress'])}\n• انجام: {delta(last['done'], prev['done'])}\n"
    max_activity = max([s["done"] for s in stats] + [s["in_progress"] for s in stats], default=1) or 1
    def ebar(n):
        filled = round(n / max_activity * 8)
        return "🟩" * filled + "⬜" * (8 - filled)
    text += "\n### 📉 فعالیت های انجام شده در ماه\n\n```\n"
    for s in stats:
        label = _month_label(s["y"], s["m"])
        text += f"{label} | انجام‌شده     | {ebar(s['done'])} {s['done']}\n{label} | در حال انجام | {ebar(s['in_progress'])} {s['in_progress']}\n"
    text += "```\n"
    await _send_rich(context, update.effective_chat.id, text)


async def report_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = await _db_call(get_all_user_tasks, update.effective_user.id)
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
        if c and f: durations.append(max(0, (f - c).total_seconds() / 86400))
    avg_days = round(sum(durations) / len(durations), 1) if durations else None
    text = ("# 📈 نرخ انجام و سرعت بستن تسک\n\n| شاخص | مقدار |\n|---|---|\n"
             f"| کل تسک‌ها | {total} |\n| انجام‌شده | {len(done)} |\n| فعال | {len(active)} |\n| لغو شده | {len(cancelled)} |\n| نرخ انجام | **{rate}%** |\n| میانگین زمان بستن | "
             + (f"**{avg_days} روز**" if avg_days is not None else "داده کافی نیست") + " |\n")
    if durations: text += f"\n📌 سریع‌ترین بستن: {round(min(durations), 1)} روز\n📌 کندترین بستن: {round(max(durations), 1)} روز\n"
    await _send_rich(context, update.effective_chat.id, text)


def _emoji_bar(pct: int, width: int = 10) -> str:
    pct = max(0, min(100, pct))
    filled = round(pct / 100 * width)
    return "🟩" * filled + "⬜" * (width - filled)


async def report_progress_bar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = await _db_call(get_all_user_tasks, update.effective_user.id)
    if not tasks:
        await query.message.reply_text("هنوز تسکی ندارید.")
        return
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("status") == "done")
    rate = round(done / total * 100) if total else 0
    by_prio = {"high": {"total": 0, "done": 0}, "medium": {"total": 0, "done": 0}, "low": {"total": 0, "done": 0}}
    for t in tasks:
        p = t.get("priority") or "low"
        if p not in by_prio: p = "low"
        by_prio[p]["total"] += 1
        if t.get("status") == "done": by_prio[p]["done"] += 1
    text = f"# 📊 نمودار پیشرفت (بارچارت ایموجی)\n\n**پیشرفت کلی:** {rate}%\n{_emoji_bar(rate)} `{done}/{total}`\n\n### بر اساس اولویت\n\n"
    for key, label in [("high", "🔴 بالا"), ("medium", "🟠 متوسط"), ("low", "🟢 پایین")]:
        st = by_prio[key]
        if st["total"] == 0:
            text += f"{label}: —\n"
            continue
        r = round(st["done"] / st["total"] * 100)
        text += f"{label}: {r}%\n{_emoji_bar(r)} `{st['done']}/{st['total']}`\n\n"
    status_counts = {"pending": 0, "in_progress": 0, "done": 0, "cancelled": 0}
    for t in tasks:
        s = t.get("status") or "pending"
        if s in status_counts: status_counts[s] += 1
    text += "### توزیع وضعیت\n\n```\n"
    max_s = max(status_counts.values()) or 1
    for key, label in [("pending", "⏳ در انتظار"), ("in_progress", "🚀 در حال انجام"), ("done", "✅ انجام‌شده"), ("cancelled", "❌ لغو")]:
        n = status_counts[key]
        filled = round(n / max_s * 8)
        text += f"{label:16} | {'█' * filled}{'░' * (8 - filled)} {n}\n"
    text += "```\n"
    await _send_rich(context, update.effective_chat.id, text)
