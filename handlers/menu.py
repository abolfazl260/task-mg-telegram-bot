from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import WEB_APP_URL

from handlers.reports import show_reports_menu
from handlers.templates import show_templates_menu
from services.user_service import get_user_timezone, set_user_timezone


TIMEZONE_CHOICES = [
    ("🇮🇷 تهران", "Asia/Tehran"),
    ("🇦🇪 دبی", "Asia/Dubai"),
    ("🇹🇷 استانبول", "Europe/Istanbul"),
    ("🇩🇪 برلین", "Europe/Berlin"),
    ("🇬🇧 لندن", "Europe/London"),
    ("🇺🇸 نیویورک", "America/New_York"),
    ("🇺🇸 لس‌آنجلس", "America/Los_Angeles"),
    ("🇨🇦 تورنتو", "America/Toronto"),
    ("🇨🇦 ونکوور", "America/Vancouver"),
]


def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ افزودن تسک",
                callback_data="add_task"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 تسک‌ها",
                callback_data="tasks"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 تیم‌ها",
                callback_data="teams"
            )
        ],
        [
            InlineKeyboardButton(
                "🧩 تمپلیت‌ها",
                callback_data="templates"
            )
        ],
        [
            InlineKeyboardButton(
                "🌱 مدیریت عادت‌ها",
                callback_data="habit_menu"
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 وب اپ",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        ],
        [
            InlineKeyboardButton(
                "📊 گزارشات",
                callback_data="stats"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 راهنما",
                callback_data="help"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات",
                callback_data="settings"
            )
        ],
        [
            InlineKeyboardButton(
                "📞 ارتباط با ما",
                callback_data="contact_us"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def tasks_options_keyboard():
    """Sub-menu when user taps Tasks — choose what to do first."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 لیست تسک‌های فعال", callback_data="tasks_list")],
        [InlineKeyboardButton("📅 مرتب‌سازی بر اساس ددلاین", callback_data="sort_deadline")],
        [InlineKeyboardButton("🎯 مرتب‌سازی بر اساس اولویت", callback_data="sort_priority")],
        [InlineKeyboardButton("🕐 مرتب‌سازی بر اساس تاریخ ایجاد", callback_data="sort_created")],
        [InlineKeyboardButton("🏷 بر اساس تگ", callback_data="report_tags")],
        [InlineKeyboardButton("📂 بر اساس دسته‌بندی", callback_data="report_category")],
        [InlineKeyboardButton("👤 بر اساس مسئول", callback_data="report_assignee")],
        [InlineKeyboardButton("📆 بر اساس هفته جاری", callback_data="report_week")],
        [InlineKeyboardButton("📥 خروجی Excel", callback_data="download_csv")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="tasks_back")],
    ])


def settings_keyboard(user_id):
    current = get_user_timezone(user_id)
    rows = []
    for label, tz_name in TIMEZONE_CHOICES:
        selected = " ✅" if tz_name == current else ""
        rows.append([InlineKeyboardButton(f"{label} ({tz_name}){selected}", callback_data=f"timezone_set_{tz_name}")])
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


async def button_handler(update, context):

    query = update.callback_query

    await query.answer()

    data = query.data

    if data == "add_task":

        await query.message.reply_text(
            "➕ افزودن تسک\n\nروش ثبت را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 ثبت تکی", callback_data="add_task_single")],
                [InlineKeyboardButton("📥 آپلود گروهی", callback_data="import_bulk")],
            ]),
        )

    elif data == "add_task_single":

        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"

        await query.message.reply_text(
            "📝 عنوان تسک را وارد کنید:"
        )

    elif data == "help":
        from handlers.help import help_command
        await help_command(update, context)

    elif data == "tasks":
        await query.message.reply_text(
            "📋 بخش تسک‌ها\n\nچه کاری می‌خواهید انجام دهید؟",
            reply_markup=tasks_options_keyboard(),
        )

    elif data == "tasks_list":
        from handlers.task import list_tasks
        await list_tasks(update, context)

    elif data == "tasks_back":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu())

    elif data == "teams":
        from handlers.team import team_command
        # simulate command without args → menu
        class _Ctx:
            args = []
            user_data = context.user_data
            bot = context.bot
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

        await query.message.reply_text(contact_text(), parse_mode="Markdown")
