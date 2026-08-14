"""UI navigation for the Telegram reports section."""

from datetime import datetime

import jdatetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import handlers.reports as reports_handler
from bot_context import get_current_bot_key
from services.task_service import get_all_user_tasks
from webapp.config import WEBAPP_BASE_URL
from webapp.report_tokens import build_report_url, create_report_token

REPORT_ROOT_CALLBACK = "report_menu"
REPORT_COUNT = 17


def _back_row():
    return [InlineKeyboardButton("🔙 بازگشت", callback_data=REPORT_ROOT_CALLBACK)]


def _web_report_url(user_id):
    bot_key = get_current_bot_key()
    token = create_report_token(bot_key, str(user_id), report_type="monthly")
    return build_report_url(WEBAPP_BASE_URL, token)


def _root_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 مشاهده گزارش تحت وب", url=_web_report_url(user_id))],
        [InlineKeyboardButton("📋 گزارش وظایف", callback_data="report_menu_tasks")],
        [InlineKeyboardButton("👥 گزارش تیم", callback_data="report_menu_team")],
        [InlineKeyboardButton("📅 تقویم و برنامه", callback_data="report_menu_calendar")],
        [InlineKeyboardButton("📈 تحلیل و عملکرد", callback_data="report_menu_analytics")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="report_back")],
    ])


def reports_root_keyboard(user_id):
    return _root_keyboard(user_id)


def _category_keyboard(rows):
    rows = list(rows)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def task_reports_keyboard():
    return _category_keyboard([
        [InlineKeyboardButton("📋 فهرست کل وظایف", callback_data="report_all")],
        [InlineKeyboardButton("📊 بر اساس وضعیت", callback_data="report_status")],
        [InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="report_priority")],
        [InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags")],
        [InlineKeyboardButton("🔥 کارهای معطل‌مانده (+۳ روز)", callback_data="report_stuck")],
    ])


def team_reports_keyboard():
    return _category_keyboard([
        [InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee")],
        [InlineKeyboardButton("🧩 برد کانبان", callback_data="report_kanban")],
    ])


def calendar_reports_keyboard():
    return _category_keyboard([
        [InlineKeyboardButton("☀️ برنامه امروز", callback_data="report_today")],
        [InlineKeyboardButton("📆 برنامه ۷ روز آینده", callback_data="report_week")],
        [InlineKeyboardButton("📅 تقویم ماه جاری", callback_data="report_calendar")],
        [InlineKeyboardButton("🔥 هیت‌مپ هفته", callback_data="report_heatmap_week")],
        [InlineKeyboardButton("🌡 هیت‌مپ ماهانه", callback_data="report_heatmap")],
    ])


def analytics_reports_keyboard():
    return _category_keyboard([
        [InlineKeyboardButton("📈 روند هفتگی", callback_data="report_trend")],
        [InlineKeyboardButton("📊 نمودار پیشرفت", callback_data="report_progress_bar")],
        [InlineKeyboardButton("📈 نرخ انجام / میانگین زمان", callback_data="report_perf")],
        [InlineKeyboardButton("📊 مقایسه سه‌ماهه", callback_data="report_compare")],
    ])


def _parse_created_at(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def _monthly_report_summary(user_id):
    now = jdatetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).togregorian()
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = next_month.togregorian()

    monthly = []
    for task in get_all_user_tasks(user_id):
        created = _parse_created_at(task.get("created_at"))
        if created and month_start <= created < month_end:
            monthly.append(task)

    counts = {"high": 0, "medium": 0, "low": 0}
    for task in monthly:
        priority = task.get("priority", "low")
        if priority not in counts:
            priority = "low"
        counts[priority] += 1
    return len(monthly), counts


def _root_text(user_id):
    try:
        total, priorities = _monthly_report_summary(user_id)
        summary = (
            f"📌 تعداد تسک‌های این ماه: **{total}**\n"
            f"🔴 اولویت بالا: **{priorities['high']}**\n"
            f"🟠 اولویت متوسط: **{priorities['medium']}**\n"
            f"🟢 اولویت پایین: **{priorities['low']}**\n\n"
        )
    except Exception:
        summary = ""

    return (
        "# 📊 گزارش‌ها\n\n"
        f"{summary}"
        f"در این بخش **{REPORT_COUNT} گزارش مختلف** برای بررسی وضعیت، برنامه و عملکرد تسک‌ها در دسترس است.\n\n"
        "دسته موردنظر را انتخاب کنید:"
    )


def _menu_text(title, description):
    return f"# {title}\n\n{description}"


async def _show_submenu(update, keyboard, title, description):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(_menu_text(title, description), reply_markup=keyboard, parse_mode="Markdown")


async def show_root_menu(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.message.edit_text(_root_text(user_id), reply_markup=_root_keyboard(user_id), parse_mode="Markdown")


async def show_task_menu(update, context):
    await _show_submenu(update, task_reports_keyboard(), "📋 گزارش وظایف", "گزارش‌های مربوط به خود وظایف را انتخاب کنید:")


async def show_team_menu(update, context):
    await _show_submenu(update, team_reports_keyboard(), "👥 گزارش تیم", "گزارش‌های مربوط به مسئولیت و عملکرد افراد:")


async def show_calendar_menu(update, context):
    await _show_submenu(update, calendar_reports_keyboard(), "📅 تقویم و برنامه", "برنامه روزانه، هفتگی و تقویم تسک‌ها:")


async def show_analytics_menu(update, context):
    await _show_submenu(update, analytics_reports_keyboard(), "📈 تحلیل و عملکرد", "تحلیل روند، پیشرفت و عملکرد تسک‌ها:")


async def show_reports_menu(update, context):
    if update.callback_query:
        await show_root_menu(update, context)
        return
    user_id = update.effective_user.id
    try:
        keyboard = _root_keyboard(user_id)
    except Exception:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 گزارش وظایف", callback_data="report_menu_tasks")],
            [InlineKeyboardButton("👥 گزارش تیم", callback_data="report_menu_team")],
            [InlineKeyboardButton("📅 تقویم و برنامه", callback_data="report_menu_calendar")],
            [InlineKeyboardButton("📈 تحلیل و عملکرد", callback_data="report_menu_analytics")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="report_back")],
        ])
    await update.message.reply_text(_root_text(user_id), reply_markup=keyboard, parse_mode="Markdown")


_original_reports_callback = reports_handler.reports_callback


async def reports_callback(update, context):
    data = update.callback_query.data
    handlers = {
        "report_menu": show_root_menu,
        "report_menu_tasks": show_task_menu,
        "report_menu_team": show_team_menu,
        "report_menu_calendar": show_calendar_menu,
        "report_menu_analytics": show_analytics_menu,
    }
    handler = handlers.get(data)
    if handler:
        await handler(update, context)
        return
    await _original_reports_callback(update, context)


reports_handler.reports_menu_keyboard = reports_root_keyboard
reports_handler.show_reports_menu = show_reports_menu
reports_handler.reports_callback = reports_callback
