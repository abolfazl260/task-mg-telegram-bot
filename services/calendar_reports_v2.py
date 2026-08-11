"""Correct calendar-grid reports using the selected user's calendar boundaries."""

from collections import defaultdict
from datetime import timedelta
import calendar
import jdatetime

from services.date_service import calendar_month_bounds, format_date, get_user_date_format_for_display, selected_calendar_today, user_today
from services.task_service import get_all_user_tasks

DAY_NAMES = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def _parse(value):
    from datetime import datetime
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _label(user_id, d):
    return format_date(d, get_user_date_format_for_display(user_id))


def _month_title(user_id):
    y, m, _ = selected_calendar_today(user_id)
    if get_user_date_format_for_display(user_id) == "gregorian":
        return f"{y}/{m:02d}"
    return f"{jdatetime.date(y, m, 1).j_months_fa[m-1]} {y}"


def _days_for_month(user_id):
    start, end = calendar_month_bounds(user_id)
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


async def report_calendar(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    month_days = _days_for_month(user_id)
    task_by_day = defaultdict(list)
    for task in tasks:
        d = _parse(task.get("deadline"))
        if d in month_days:
            task_by_day[d].append(task)

    text = f"# 📅 تقویم تسک‌ها — {_month_title(user_id)}\n\n"
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n|---|---|---|---|---|---|---|\n"
    weeks = [[]]
    first = month_days[0]
    leading = (first.weekday() - 5) % 7
    weeks[0] = [None] * leading
    for d in month_days:
        if len(weeks[-1]) == 7:
            weeks.append([])
        weeks[-1].append(d)
    while len(weeks[-1]) < 7:
        weeks[-1].append(None)

    for week in weeks:
        cells = []
        for d in week:
            if d is None:
                cells.append(" ")
                continue
            cell = f"**{_label(user_id, d).split('/')[-1]}**"
            items = task_by_day.get(d, [])
            if items:
                lines = "<br>".join(t.get("title", "-") for t in items[:2])
                if len(items) > 2:
                    lines += f"<br>+{len(items)-2} مورد"
                cell += "<br>" + lines
            cells.append(cell)
        text += "| " + " | ".join(cells) + " |\n"

    if task_by_day:
        text += "\n\n### 📌 تسک‌های این ماه\n\n| تاریخ | عنوان تسک‌ها |\n|---|---|\n"
        for d in sorted(task_by_day):
            text += f"| {_label(user_id, d)} | {' — '.join(t.get('title','-') for t in task_by_day[d])} |\n"
    else:
        text += "\n\n_در این ماه تسکی با مهلت ثبت‌شده وجود ندارد._"
    await context.bot._post("sendRichMessage", data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}})


async def report_heatmap(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = get_all_user_tasks(user_id)
    month_days = _days_for_month(user_id)
    counts = defaultdict(int)
    for task in tasks:
        d = _parse(task.get("deadline"))
        if d in month_days:
            counts[d] += 1
    max_c = max(counts.values(), default=0)

    def intensity(n):
        if not n or not max_c:
            return "⬜"
        r = n / max_c
        return "🟩" if r <= .25 else "🟨" if r <= .5 else "🟧" if r <= .75 else "🟥"

    text = f"# 🌡 هیت‌مپ ماهانه — {_month_title(user_id)}\n\n"
    text += "| شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه |\n| :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    first = month_days[0]
    leading = (first.weekday() - 5) % 7
    week = [None] * leading
    weeks = []
    for d in month_days:
        if len(week) == 7:
            weeks.append(week)
            week = []
        week.append(d)
    while len(week) < 7:
        week.append(None)
    weeks.append(week)
    for row in weeks:
        cells = []
        for d in row:
            if d is None:
                cells.append("·")
                continue
            day_num = _label(user_id, d).split('/')[-1]
            n = counts[d]
            cells.append(f"{intensity(n)}<br>**{day_num}**<br>({n})")
        text += "| " + " | ".join(cells) + " |\n"
    text += "\n\n📌 مرز ماه و شماره روزها بر اساس تقویم انتخاب‌شده محاسبه شده و تاریخ‌های داخلی همچنان Gregorian هستند."
    await context.bot._post("sendRichMessage", data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}})



def _install_calendar_pdf_routes() -> None:
    """Add the PDF export to the existing reports UI without changing its dispatcher contract."""
    from handlers import reports as reports_handler
    from handlers.calendar_pdf import calendar_pdf_callback

    if getattr(reports_handler, "_calendar_pdf_routes_installed", False):
        return

    original_menu = reports_handler.reports_menu_keyboard

    def reports_menu_with_calendar_pdf():
        markup = original_menu()
        rows = [list(row) for row in markup.inline_keyboard]
        if not any(button.callback_data == "report_calendar_pdf" for row in rows for button in row):
            rows.append([reports_handler.InlineKeyboardButton("📄 خروجی PDF تقویم ماهانه", callback_data="report_calendar_pdf")])
        return reports_handler.InlineKeyboardMarkup(rows)

    original_callback = reports_handler.reports_callback

    async def reports_callback_with_calendar_pdf(update, context):
        if update.callback_query and update.callback_query.data == "report_calendar_pdf":
            await calendar_pdf_callback(update, context)
            return
        await original_callback(update, context)

    reports_handler.reports_menu_keyboard = reports_menu_with_calendar_pdf
    reports_handler.reports_callback = reports_callback_with_calendar_pdf
    reports_handler._calendar_pdf_routes_installed = True


_install_calendar_pdf_routes()
