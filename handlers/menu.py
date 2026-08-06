from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():

    keyboard=[
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
                "📊 آمار",
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

    return InlineKeyboardMarkup(
        keyboard
    )


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

        await query.message.reply_text(
            "📋 /tasks را اجرا کنید"
        )

    elif data == "stats":

        await query.message.reply_text(
            "📊 آمار"
        )

    elif data == "settings":

        await query.message.reply_text(
            "⚙️ تنظیمات"
        )