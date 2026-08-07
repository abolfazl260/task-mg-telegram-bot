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
        ],
        [
            InlineKeyboardButton(
                "⏭ رد کردن (متوسط)",
                callback_data="priority_skip"
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
        ],
        [
            InlineKeyboardButton(
                "⏳ بدون زمان‌بندی",
                callback_data="deadline_none"
            )
        ]
    ])


def task_action_keyboard(task_id: str, current_status: str = "pending"):
    """Action buttons based on current task status."""

    buttons = []

    if current_status == "pending":
        buttons.append([
            InlineKeyboardButton(
                "🚀 شروع",
                callback_data=f"start_{task_id}"
            )
        ])

    if current_status in ("pending", "in_progress"):
        buttons.append([
            InlineKeyboardButton(
                "✅ انجام شد",
                callback_data=f"done_{task_id}"
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                "❌ لغو",
                callback_data=f"cancel_{task_id}"
            )
        ])

    if current_status == "in_progress":
        buttons.insert(0, [
            InlineKeyboardButton(
                "⏸ بازگشت به انتظار",
                callback_data=f"pending_{task_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("👤 مسئول", callback_data=f"owner_{task_id}")
    ])
    buttons.append([
        InlineKeyboardButton("🙋 برعهده گرفتن", callback_data=f"take_{task_id}")
    ])

    return InlineKeyboardMarkup(buttons)
