"""UI navigation for the Telegram reports section.

Keeps the existing report handlers intact and only reorganizes their presentation
into four user-facing categories.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import handlers.reports as reports_handler


REPORT_ROOT_CALLBACK = "report_menu"


def _back_row():
    return [InlineKeyboardButton("🔙 بازگشت", callback_data=REPORT_ROOT_CALLBACK)]


def _category_keyboard(rows):
    rows = list(rows)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def reports_root_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 گزارش وظایف", callback_data="report_menu_tasks")],
        [InlineKeyboardButton("👥 گزارش تیم", callback_data="report_menu_team")],
        [InlineKeyboardButton("📅 تقویم و برنامه", callback_data="report_menu_calendar")],
        [InlineKeyboardButton("📈 تحلیل و عملکرد", callback_data="report_menu_analytics")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="report_back")],
    ])


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


def _menu_text(title, description):
    return f"# {title}\n\n{description}"


async def _show_submenu(update, keyboard, title, description):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        _menu_text(title, description),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def show_root_menu(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "# 📊 گزارش‌ها\n\nدسته موردنظر را انتخاب کنید:",
        reply_markup=reports_root_keyboard(),
        parse_mode="Markdown",
    )


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
    await update.message.reply_text(
        "# 📊 گزارش‌ها\n\nدسته موردنظر را انتخاب کنید:",
        reply_markup=reports_root_keyboard(),
        parse_mode="Markdown",
    )


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


# Patch only the UI entry points. Individual report implementations remain unchanged.
reports_handler.reports_menu_keyboard = reports_root_keyboard
reports_handler.show_reports_menu = show_reports_menu
reports_handler.reports_callback = reports_callback
