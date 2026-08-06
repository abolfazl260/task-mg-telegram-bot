from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.task import list_tasks, add_task
from handlers.reports import show_reports_menu


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

        # reuse list_tasks by faking a message-like call
        # create a simple wrapper
        class FakeMessage:
            def __init__(self, original):
                self.chat = original.chat
                self.message_id = original.message_id
                self.from_user = original.from_user

            async def reply_text(self, *args, **kwargs):
                return await original.reply_text(*args, **kwargs)

            async def reply_document(self, *args, **kwargs):
                return await original.reply_document(*args, **kwargs)

        original = query.message
        fake_update = update
        # list_tasks expects update.message
        # we temporarily set it
        old_message = update.message
        update.message = original

        try:
            await list_tasks(update, context)
        finally:
            update.message = old_message

    elif data == "stats":

        await show_reports_menu(update, context)

    elif data == "settings":

        await query.message.reply_text(
            "⚙️ تنظیمات\n\nبه زودی در دسترس خواهد بود."
        )
