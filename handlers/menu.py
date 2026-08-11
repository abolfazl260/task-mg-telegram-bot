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
    keyboard.append([InlineKeyboardButton("🏠 شروع / منوی اصلی", callback_data="start_menu")])
    return InlineKeyboardMarkup(keyboard)


def tasks_options_keyboard(context=None):
    """Compact Tasks submenu: one full-width row, then paired rows, then back."""
    profile = _bot_profile(context)
    rows = [
        [InlineKeyboardButton("📋 لیست تسک‌های فعال", callback_data="tasks_list")],
        [
            InlineKeyboardButton("📅 بر اساس ددلاین", callback_data="sort_deadline"),
            InlineKeyboardButton("🎯 بر اساس اولویت", callback_data="sort_priority"),
        ],
        [
            InlineKeyboardButton("🕒 تاریخ ایجاد", callback_data="sort_created"),
            InlineKeyboardButton("📅 هفته جاری", callback_data="report_week"),
        ],
        [
            InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags"),
            InlineKeyboardButton("📁 دسته‌بندی", callback_data="report_category"),
        ],
        [
            InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee"),
            InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv"),
        ],
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
    return (
        "🗓 **تنظیمات تقویم**\n\n"
        f"تقویم فعال: **{label}**\n\n"
        "لطفا تقویم مورد نظر خود را برای نمایش تاریخ تسک‌ها و گزارش‌ها انتخاب کنید."
    )


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
    rows = [
        [InlineKeyboardButton(f"⭐️ دونیت {amount} استارز", callback_data=f"donate_{amount}")]
        for amount in DONATION_AMOUNTS
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="tasks_back")])
    return InlineKeyboardMarkup(rows)


async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data
    profile = _bot_profile(context)
    feature_by_callback = {
        "add_task": "tasks", "tasks": "tasks", "teams": "teams",
        "templates": "templates", "habit_menu": "habits", "stats": "reports",
        "import_bulk": "bulk_import", "custom_bot": "custom_bots",
    }
    required_feature = feature_by_callback.get(data)
    if profile is not None and required_feature and not profile.feature_enabled(required_feature):
        await query.message.reply_text("⚠️ این قابلیت برای این ربات فعال نیست.")
        return

    if data.startswith("view_tasks_") or data.startswith("tasks_filter_"):
        from handlers.task_pagination import tasks_view_callback
        # tasks_view_callback answers the callback itself for filter navigation.
        # The initial answer above is harmless and keeps the UI responsive.
        await tasks_view_callback(update, context)
        return
    if data == "start_menu":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu(context))
    elif data == "add_task":
        await query.message.reply_text(
            "➕ افزودن تسک\n\nروش ثبت را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📝 ثبت تکی", callback_data="add_task_single")]]
                + ([[InlineKeyboardButton("📥 آپلود گروهی", callback_data="import_bulk")]] if _feature_enabled(profile, "bulk_import") else [])
            ),
        )
    elif data == "add_task_single":
        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"
        await query.message.reply_text("📝 عنوان تسک را وارد کنید:")
    elif data == "custom_bot":
        from handlers.custom_bot import show_custom_bot_menu
        await show_custom_bot_menu(update, context)
    elif data == "help":
        from handlers.help import help_command
        await help_command(update, context)
    elif data == "tasks":
        await query.message.reply_text(
            "📋 بخش مدیریت تسک‌ها\n\nجهت مشاهده، مرتب‌سازی یا دریافت خروجی، یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=tasks_options_keyboard(context),
        )
    elif data == "tasks_list":
        from handlers.task import list_tasks
        await list_tasks(update, context)
    elif data == "tasks_back":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu(context))
    elif data == "teams":
        from handlers.team import team_command
        await team_command(update, context)
    elif data == "habit_menu":
        from handlers.habits import show_habit_menu
        await show_habit_menu(update, context)
    elif data == "templates":
        await show_templates_menu(update, context)
    elif data == "stats":
        await show_reports_menu(update, context)
    elif data == "import_bulk":
        from handlers.import_bulk import start_import_flow
        await start_import_flow(update, context)
    elif data == "settings":
        await query.message.reply_text(
            "⚙️ **تنظیمات**\n\nبخش موردنظر خود را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(context),
        )
    elif data == "settings_timezone":
        await query.message.reply_text(
            timezone_text(update.effective_user.id),
            parse_mode="Markdown",
            reply_markup=timezone_keyboard(update.effective_user.id),
        )
    elif data == "settings_date_format":
        await query.message.reply_text(
            date_format_text(update.effective_user.id),
            parse_mode="Markdown",
            reply_markup=date_format_keyboard(update.effective_user.id),
        )
    elif data in {"date_format_jalali", "date_format_gregorian"}:
        selected = data.replace("date_format_", "", 1)
        if set_user_date_format(update.effective_user.id, selected):
            await query.message.reply_text(
                "✅ تقویم نمایش تاریخ تغییر کرد.",
                reply_markup=date_format_keyboard(update.effective_user.id),
            )
        else:
            await query.message.reply_text("⚠️ ذخیره نوع تاریخ ناموفق بود.")
    elif data == "settings_language":
        await query.message.reply_text(
            "🌐 **تغییر زبان**\n\nانتخاب زبان در نسخه بعدی فعال خواهد شد.",
            parse_mode="Markdown",
            reply_markup=language_keyboard(),
        )
    elif data in {"language_fa", "language_en"}:
        await query.answer("این قابلیت در نسخه بعدی فعال می‌شود.", show_alert=True)
    elif data == "integrations":
        await show_integrations(update, context)
    elif data.startswith("timezone_set_"):
        tz_name = data.replace("timezone_set_", "", 1)
        if tz_name not in VALID_TIMEZONES:
            await query.message.reply_text("⚠️ منطقه زمانی نامعتبر است.")
            return
        if set_user_timezone(update.effective_user.id, tz_name):
            await query.message.reply_text(
                f"✅ زمان محلی شما روی {tz_name} تنظیم شد. از این پس یادآوری‌ها با ساعت محلی شما ارسال می‌شوند.",
                reply_markup=timezone_keyboard(update.effective_user.id),
            )
        else:
            await query.message.reply_text("⚠️ ذخیره منطقه زمانی ناموفق بود.")
    elif data == "contact_us":
        await query.message.reply_text(contact_text(), parse_mode="Markdown", reply_markup=contact_keyboard())
