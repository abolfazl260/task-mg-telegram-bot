from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def priority_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔴 بالا",
                callback_data="priority_high"
            )
        ],
        [
            InlineKeyboardButton(
                "🟠 متوسط",
                callback_data="priority_medium"
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 پایین",
                callback_data="priority_low"
            )
        ]
    ])



def deadline_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📅 فردا",
                callback_data="deadline_1"
            )
        ],
        [
            InlineKeyboardButton(
                "📅 ۳ روز دیگر",
                callback_data="deadline_3"
            )
        ],
        [
            InlineKeyboardButton(
                "📅 ۱ هفته دیگر",
                callback_data="deadline_7"
            )
        ],
        [
            InlineKeyboardButton(
                "📅 ۲ هفته دیگر",
                callback_data="deadline_14"
            )
        ],
        [
            InlineKeyboardButton(
                "📅 ۳ هفته دیگر",
                callback_data="deadline_21"
            )
        ],
        [
            InlineKeyboardButton(
                "✍️ تاریخ دقیق",
                callback_data="deadline_custom"
            )
        ]
    ])



def task_action_keyboard(task_id):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 شروع",
                callback_data=f"start_{task_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ انجام شد",
                callback_data=f"done_{task_id}"
            )
        ]
    ])