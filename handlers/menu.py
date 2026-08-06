from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.task import list_tasks
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
                "⚙️ تنظیمات",
                callback_data="settings"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


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

        old_message = update.message
        update.message = query.message

        try:
            await list_tasks(update, context)
        finally:
            update.message = old_message

    elif data == "templates":

        await show_templates_menu(update, context)

    elif data == "stats":

        await show_reports_menu(update, context)

    elif data == "settings":

        await query.message.reply_text(
            "⚙️ تنظیمات\n\nبه زودی در دسترس خواهد بود."
        )
