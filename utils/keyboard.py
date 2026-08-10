from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def priority_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 بالا", callback_data="priority_high")],
        [InlineKeyboardButton("🟠 متوسط", callback_data="priority_medium")],
        [InlineKeyboardButton("🟢 پایین", callback_data="priority_low")],
    ])


def deadline_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 فردا", callback_data="deadline_1")],
        [InlineKeyboardButton("📅 ۳ روز دیگر", callback_data="deadline_3")],
        [InlineKeyboardButton("📅 ۱ هفته دیگر", callback_data="deadline_7")],
        [InlineKeyboardButton("📅 ۲ هفته دیگر", callback_data="deadline_14")],
        [InlineKeyboardButton("📅 ۳ هفته دیگر", callback_data="deadline_21")],
        [InlineKeyboardButton("✍️ تاریخ دقیق", callback_data="deadline_custom")],
        [InlineKeyboardButton("⏳ بدون زمان‌بندی", callback_data="deadline_none")],
    ])


def task_action_keyboard(task_id: str, current_status: str = "pending", bot_profile=None, comment_count: int = 0):
    """Compact task-card actions grouped into logical rows."""
    labels = {}
    if bot_profile is not None:
        labels = bot_profile.workflow.get("actions", {})

    buttons = []

    status_row = []
    if current_status == "pending":
        status_row.append(InlineKeyboardButton(labels.get("start", "🚀 شروع"), callback_data=f"start_{task_id}"))
    if current_status in ("pending", "in_progress"):
        status_row.append(InlineKeyboardButton(labels.get("done", "✅ انجام شد"), callback_data=f"done_{task_id}"))
        status_row.append(InlineKeyboardButton(labels.get("cancel", "❌ لغو"), callback_data=f"cancel_{task_id}"))
    if current_status == "in_progress":
        # Keep the return-to-pending action available without making the card tall.
        buttons.append([InlineKeyboardButton(labels.get("pending", "⏸ بازگشت به انتظار"), callback_data=f"pending_{task_id}")])
    if status_row:
        buttons.append(status_row)

    buttons.append([
        InlineKeyboardButton(f"💬 کامنت ({comment_count})", callback_data=f"comment_add_{task_id}"),
        InlineKeyboardButton(labels.get("details", "🔍 جزئیات و تاریخچه"), callback_data=f"task_details_{task_id}"),
    ])
    buttons.append([
        InlineKeyboardButton(labels.get("owner", "👤 تغییر مسئول"), callback_data=f"owner_{task_id}"),
        InlineKeyboardButton(labels.get("take", "🙋‍♂️ برعهده گرفتن"), callback_data=f"take_{task_id}"),
    ])

    return InlineKeyboardMarkup(buttons)
