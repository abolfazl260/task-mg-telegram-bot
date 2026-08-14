from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.reports import show_reports_menu
from handlers.donate import DONATION_AMOUNTS
from handlers.templates import show_templates_menu
from handlers.integrations import show_integrations
from services.timezone_service import (
    VALID_TIMEZONES,
    build_timezone_keyboard,
    build_timezone_text,
    set_user_timezone,
)
from services.user_service import get_user_date_format, set_user_date_format


def _bot_profile(context=None):
    if context is not None:
        return context.bot_data.get("bot_config")
    return None


def _feature_enabled(profile, feature):
    return not feature or profile is None or profile.feature_enabled(feature)


def main_menu(context=None):
    profile = _bot_profile(context)
    menu_items = profile.menu if profile is not None else []
    if not menu_items:
        from bot_platform import DEFAULT_MENU
        menu_items = DEFAULT_MENU
    keyboard = []
    for item in menu_items:
        if _feature_enabled(profile, item.get("feature")):
            keyboard.append([InlineKeyboardButton(item["label"], callback_data=item["callback_data"])])
    return InlineKeyboardMarkup(keyboard)


def tasks_options_keyboard(context=None):
    """Compact Tasks submenu: one full-width row, then paired rows, then back."""
    profile = _bot_profile(context)
    rows = [
        [InlineKeyboardButton("📋 لیست تسک‌های فعال", callback_data="tasks_list")],
        [InlineKeyboardButton("📅 بر اساس ددلاین", callback_data="sort_deadline"), InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="sort_priority")],
        [InlineKeyboardButton("🕒 تاریخ ایجاد", callback_data="sort_created"), InlineKeyboardButton("📅 هفته جاری", callback_data="report_week")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags"), InlineKeyboardButton("📁 دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee"), InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="tasks_back")],
    ]
    if profile is not None and not profile.feature_enabled("unassigned"):
        rows[4] = [rows[4][1]]
    return InlineKeyboardMarkup(rows)


def settings_keyboard(context=None):
    """Top-level settings categories; detailed settings open only after selection."""
    profile = _bot_profile(context)
    rows = []
    if _feature_enabled(profile, "integrations"):
        rows.append([InlineKeyboardButton("🔗 اتصال به سرویس‌های مدیریت تسک", callback_data="integrations")])
    rows.append([InlineKeyboardButton("🌍 زمان محلی", callback_data="settings_timezone")])
    rows.append([InlineKeyboardButton("📅 نوع تاریخ", callback_data="settings_date_format")])
    rows.append([InlineKeyboardButton("🌐 تغییر زبان", callback_data="settings_language")])
    if _feature_enabled(profile, "custom_bots"):
        rows.append([InlineKeyboardButton("🤖 ساخت ربات اختصاصی", callback_data="custom_bot")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="tasks_back")])
    return InlineKeyboardMarkup(rows)


def timezone_keyboard(user_id):
    rows = build_timezone_keyboard(user_id, InlineKeyboardButton)
    rows.append([InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


def timezone_text(user_id):
    return build_timezone_text(user_id)


def date_format_keyboard(user_id):
    current = get_user_date_format(user_id)
    jalali = "✅ شمسی 🇮🇷" if current == "jalali" else "شمسی 🇮🇷"
    gregorian = "✅ میلادی 🌐" if current == "gregorian" else "میلادی 🌐"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(jalali, callback_data="date_format_jalali")],
        [InlineKeyboardButton(gregorian, callback_data="date_format_gregorian")],
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="settings")],
    ])


def date_format_text(user_id):
    current = get_user_date_format(user_id)
    label = "شمسی 🇮🇷" if current == "jalali" else "میلادی 🌐"
    return f"🗓 **تنظیمات تقویم**\n\nتقویم فعال: **{label}**\n\nلطفا تقویم مورد نظر خود را برای نمایش تاریخ تسک‌ها و گزارش‌ها انتخاب کنید."


def language_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data="language_fa")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="language_en")],
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="settings")],
    ])


def contact_text():
    return (
        "📞 **ارتباط با ما**\n"
        "این ربات با هدف **مدیریت ساده‌تر و بهتر وظایف** توسعه داده شده است. نگهداری، بهبود و اضافه‌کردن قابلیت‌های جدید، نیازمند صرف زمان و هزینه است.\n"
        "💙 اگر از ربات استفاده می‌کنید و مایل به **حمایت مالی از توسعه و ادامه فعالیت آن** هستید، خوشحال می‌شویم با ما در ارتباط باشید.\n"
        "💡 **ایده یا پیشنهاد دارید؟**\n"
        "اگر قابلیت، ایده یا نیاز خاصی در نظر دارید، برای ما ارسال کنید تا در توسعه نسخه‌های آینده بررسی شود.\n"
        "🤖 **ربات اختصاصی برای کسب‌وکار شما**\n"
        "اگر می‌خواهید این ربات متناسب با نیازهای کسب‌وکار شما **شخصی‌سازی و اختصاصی‌سازی** شود، برای همکاری با ما در ارتباط باشید:\n"
        "👉 @abolfazl\\_rezaiee\n"
        "📣 **سایر ربات‌ها و خدمات ما**\n"
        "✈️ **خدمات جامع مسافران هوایی**\n"
        "🎫 تضمین **بهترین نرخ پرواز، بدون واسطه**\n"
        "👉 @Flightiranbot\n"
        "📦 **ارسال سریع بار هوایی**\n"
        "👉 @koolbar\\_international\n"
        "🏠 **بهترین راه برای پیدا کردن خانه در کانادا**\n"
        "👉 @Machino24bot\n"
        "👉 @canadahouse24"
    )


def contact_keyboard():
    rows = [[InlineKeyboardButton(f"⭐️ دونیت {amount} استارز", callback_data=f"donate_{amount}")] for amount in DONATION_AMOUNTS]
    rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="tasks_back")])
    return InlineKeyboardMarkup(rows)


async def button_handler(update, context):
    query = update.callback_query
    data = query.data

    # Dedicated callback families own their callback acknowledgement.
    if data == "report_calendar_pdf":
        from handlers.calendar_pdf import calendar_pdf_callback
        return await calendar_pdf_callback(update, context)
    if data.startswith("report_"):
        from handlers.reports import reports_callback
        return await reports_callback(update, context)

    if data.startswith(("ai_task_", "ai_habit_")):
        from handlers.ai import ai_habit_callback, ai_task_callback
        if data.startswith("ai_habit_"):
            return await ai_habit_callback(update, context)
        return await ai_task_callback(update, context)

    if data.startswith("habit_"):
        from handlers.habits import handle_habit_callback
        return await handle_habit_callback(update, context)

    profile = _bot_profile(context)
    feature_by_callback = {
        "add_task": "tasks", "tasks": "tasks", "teams": "teams",
        "templates": "templates", "habit_menu": "habits", "stats": "reports",
        "import_bulk": "bulk_import", "custom_bot": "custom_bots",
    }
    feature = feature_by_callback.get(data)
    if feature and not _feature_enabled(profile, feature):
        await query.answer("این قابلیت برای این ربات فعال نیست.", show_alert=True)
        return

    await query.answer()

    if data == "add_task":
        from handlers.task import add_task
        return await add_task(update, context)
    if data == "tasks":
        return await query.message.reply_text("📋 **منوی تسک‌ها**", reply_markup=tasks_options_keyboard(context), parse_mode="Markdown")
    if data == "tasks_list":
        from handlers.task_pagination import paginated_list_tasks
        return await paginated_list_tasks(update, context)
    if data == "teams":
        from handlers.team import team_command
        return await team_command(update, context)
    if data == "templates":
        return await show_templates_menu(update, context)
    if data == "habit_menu":
        from handlers.habits import show_habit_menu
        return await show_habit_menu(update, context)
    if data == "stats":
        return await show_reports_menu(update, context)
    if data == "help":
        from handlers.help import help_command
        return await help_command(update, context)
    if data == "settings":
        return await query.message.reply_text("⚙️ **تنظیمات**", reply_markup=settings_keyboard(context), parse_mode="Markdown")
    if data == "settings_timezone":
        return await query.message.reply_text(timezone_text(update.effective_user.id), reply_markup=timezone_keyboard(update.effective_user.id), parse_mode="Markdown")
    if data == "settings_date_format":
        return await query.message.reply_text(date_format_text(update.effective_user.id), reply_markup=date_format_keyboard(update.effective_user.id), parse_mode="Markdown")
    if data == "settings_language":
        return await query.message.reply_text("🌐 **تغییر زبان**\n\nزبان مورد نظر خود را انتخاب کنید:", reply_markup=language_keyboard(), parse_mode="Markdown")
    if data in {"date_format_jalali", "date_format_gregorian"}:
        set_user_date_format(update.effective_user.id, "jalali" if data.endswith("jalali") else "gregorian")
        return await query.message.reply_text(date_format_text(update.effective_user.id), reply_markup=date_format_keyboard(update.effective_user.id), parse_mode="Markdown")
    if data in {"language_fa", "language_en"}:
        await query.answer("تغییر زبان در نسخه فعلی هنوز فعال نشده است.", show_alert=True)
        return
    if data == "integrations":
        return await show_integrations(update, context)
    if data == "custom_bot":
        from handlers.custom_bot import custom_bot_callback
        return await custom_bot_callback(update, context)
    if data == "import_bulk":
        from handlers.import_bulk import import_callback
        return await import_callback(update, context)
    if data == "download_csv":
        from handlers.task import download_csv
        return await download_csv(update, context)
    if data == "contact_us":
        return await query.message.reply_text(contact_text(), reply_markup=contact_keyboard(), parse_mode="Markdown")
    if data == "tasks_back":
        return await query.message.reply_text("منوی اصلی:", reply_markup=main_menu(context))

    # Unknown callback: acknowledge it instead of leaving the button spinning.
    await query.answer("این گزینه در نسخه فعلی در دسترس نیست.", show_alert=True)
