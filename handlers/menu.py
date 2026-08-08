from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.reports import show_reports_menu
from handlers.donate import DONATION_AMOUNTS
from handlers.templates import show_templates_menu
from services.user_service import get_user_timezone, set_user_timezone
from handlers.integrations import show_integrations


# فهرست مناطق زمانی قابل انتخاب؛ نام شهر برای نمایش به کاربر است و مقدار دوم
# منطقه زمانی واقعی IANA است که برای محاسبه ساعت و یادآوری‌ها استفاده می‌شود.
TIMEZONE_CHOICES = [
    ("🇮🇷 تهران", "Asia/Tehran"),
    ("🇮🇷 مشهد", "Asia/Tehran"),
    ("🇮🇷 اصفهان", "Asia/Tehran"),
    ("🇮🇷 شیراز", "Asia/Tehran"),
    ("🇮🇷 تبریز", "Asia/Tehran"),
    ("🇮🇷 کرج", "Asia/Tehran"),
    ("🇮🇷 اهواز", "Asia/Tehran"),
    ("🇮🇷 قم", "Asia/Tehran"),
    ("🇮🇷 رشت", "Asia/Tehran"),
    ("🇮🇷 کرمان", "Asia/Tehran"),
    ("🇮🇷 یزد", "Asia/Tehran"),
    ("🇮🇷 ارومیه", "Asia/Tehran"),
    ("🇮🇷 کرمانشاه", "Asia/Tehran"),
    ("🇦🇫 کابل", "Asia/Kabul"),
    ("🇦🇫 هرات", "Asia/Kabul"),
    ("🇹🇯 دوشنبه", "Asia/Dushanbe"),
    ("🇦🇪 دبی", "Asia/Dubai"),
    ("🇹🇷 استانبول", "Europe/Istanbul"),
    ("🇷🇺 مسکو", "Europe/Moscow"),
    ("🇷🇺 سن‌پترزبورگ", "Europe/Moscow"),
    ("🇷🇺 کازان", "Europe/Moscow"),
    ("🇷🇺 نیژنی نووگورود", "Europe/Moscow"),
    ("🇷🇺 سامارا", "Europe/Samara"),
    ("🇷🇺 یکاترینبورگ", "Asia/Yekaterinburg"),
    ("🇷🇺 نووسیبیرسک", "Asia/Novosibirsk"),
    ("🇷🇺 کراسنویارسک", "Asia/Krasnoyarsk"),
    ("🇷🇺 ایرکوتسک", "Asia/Irkutsk"),
    ("🇷🇺 ولادی‌وستوک", "Asia/Vladivostok"),
    ("🇩🇪 برلین", "Europe/Berlin"),
    ("🇬🇧 لندن", "Europe/London"),
    ("🇺🇸 نیویورک", "America/New_York"),
    ("🇺🇸 لس‌آنجلس", "America/Los_Angeles"),
    ("🇨🇦 تورنتو", "America/Toronto"),
    ("🇨🇦 ونکوور", "America/Vancouver"),
]


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

    # اتصال به سرویس‌های مدیریت تسک باید در منوی اصلی و جدا از تنظیمات باشد.
    keyboard.append([InlineKeyboardButton("🔗 اتصال به سرویس‌های مدیریت تسک", callback_data="integrations")])
    return InlineKeyboardMarkup(keyboard)


def tasks_options_keyboard(context=None):
    """Sub-menu when user taps Tasks — choose what to do first."""
    profile = _bot_profile(context)
    rows = [
        [InlineKeyboardButton("📋 لیست تسک‌های فعال", callback_data="tasks_list")],
        [InlineKeyboardButton("📅 مرتب‌سازی بر اساس ددلاین", callback_data="sort_deadline")],
        [InlineKeyboardButton("🎯 مرتب‌سازی بر اساس اولویت", callback_data="sort_priority")],
        [InlineKeyboardButton("🕐 مرتب‌سازی بر اساس تاریخ ایجاد", callback_data="sort_created")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags")],
        [InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee")],
        [InlineKeyboardButton("📆 بر اساس هفته جاری", callback_data="report_week")],
        [InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")],
    ]
    if profile is not None and not profile.feature_enabled("unassigned"):
        rows = [row for row in rows if "مسئول" not in row[0].text]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="tasks_back")])
    return InlineKeyboardMarkup(rows)


def settings_keyboard(user_id):
    current = get_user_timezone(user_id)
    rows = []
    for label, tz_name in TIMEZONE_CHOICES:
        selected = " ✅" if tz_name == current else ""
        rows.append([InlineKeyboardButton(f"{label}{selected}", callback_data=f"timezone_set_{tz_name}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="tasks_back")])
    return InlineKeyboardMarkup(rows)


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

    if data == "add_task":
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
        await query.message.reply_text("📋 بخش تسک‌ها\n\nچه کاری می‌خواهید انجام دهید؟", reply_markup=tasks_options_keyboard(context))
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
        current = get_user_timezone(update.effective_user.id)
        await query.message.reply_text(
            f"⚙️ تنظیمات\n\n🌍 زمان محلی فعلی: {current}\n\nمنطقه زمانی خود را انتخاب کنید:",
            reply_markup=settings_keyboard(update.effective_user.id),
        )
    elif data == "integrations":
        await show_integrations(update, context)
    elif data.startswith("timezone_set_"):
        tz_name = data.replace("timezone_set_", "", 1)
        if set_user_timezone(update.effective_user.id, tz_name):
            await query.message.reply_text(
                f"✅ زمان محلی شما روی {tz_name} تنظیم شد. از این پس یادآوری‌ها با ساعت محلی شما ارسال می‌شوند.",
                reply_markup=settings_keyboard(update.effective_user.id),
            )
        else:
            await query.message.reply_text("⚠️ منطقه زمانی نامعتبر است.")
    elif data == "contact_us":
        await query.message.reply_text(contact_text(), parse_mode="Markdown", reply_markup=contact_keyboard())
