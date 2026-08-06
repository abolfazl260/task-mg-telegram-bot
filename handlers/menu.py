from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.reports import show_reports_menu
from handlers.templates import show_templates_menu


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
                "🧩 تمپلیت‌ها",
                callback_data="templates"
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
                "📥 ایمپورت گروهی",
                callback_data="import_bulk"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات",
                callback_data="settings"
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
        [InlineKeyboardButton("📥 دانلود CSV", callback_data="download_csv")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="tasks_back")],
    ])


async def button_handler(update, context):

    query = update.callback_query

    await query.answer()

    data = query.data

    if data == "add_task":

        context.user_data["new_task"] = {}
        context.user_data["step"] = "title"

        await query.message.reply_text(
            "📝 عنوان تسک را وارد کنید:"
        )

    elif data == "tasks":
        # Show options first — do not dump everything
        await query.message.reply_text(
            "📋 بخش تسک‌ها\n\nچه کاری می‌خواهید انجام دهید؟",
            reply_markup=tasks_options_keyboard(),
        )

    elif data == "tasks_list":
        from handlers.task import list_tasks
        old_message = update.message
        update.message = query.message
        try:
            await list_tasks(update, context)
        finally:
            update.message = old_message

    elif data == "tasks_back":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu())

    elif data == "templates":

        await show_templates_menu(update, context)

    elif data == "stats":

        await show_reports_menu(update, context)

    elif data == "import_bulk":
        from handlers.import_bulk import start_import_flow
        await start_import_flow(update, context)

    elif data == "settings":

        await query.message.reply_text(
            "⚙️ تنظیمات\n\nبه زودی در دسترس خواهد بود."
        )
