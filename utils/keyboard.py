from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.database import get_db


async def recent_tag_keyboard(user_id: int, limit: int = 6):
    """Build the tag-selection keyboard from the user's recently used tags."""
    db = await get_db()
    async with db.conn.execute(
        """
        SELECT tags
        FROM tasks
        WHERE user_id = ? AND tags IS NOT NULL AND TRIM(tags) <> ''
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (str(user_id),),
    ) as cursor:
        rows = await cursor.fetchall()

    recent_tags = []
    seen = set()
    for row in rows:
        raw = row[0] or ""
        for tag in str(raw).replace("\n", ",").replace("،", ",").split(","):
            tag = tag.strip().lstrip("#")
            if not tag:
                continue
            key = tag.casefold()
            if key in seen:
                continue
            seen.add(key)
            recent_tags.append(tag)
            if len(recent_tags) >= limit:
                break
        if len(recent_tags) >= limit:
            break

    rows = []
    for index in range(0, len(recent_tags), 2):
        rows.append([
            InlineKeyboardButton(
                f"🏷 {tag}",
                callback_data=f"tag_pick_{index + offset}",
            )
            for offset, tag in enumerate(recent_tags[index:index + 2])
        ])

    rows.append([
        InlineKeyboardButton("➕ تایپ تگ جدید", callback_data="tag_new"),
    ])
    rows.append([
        InlineKeyboardButton("⏭ بدون تگ (رد شدن)", callback_data="tag_none"),
        InlineKeyboardButton("🔙 مرحله قبل", callback_data="step_back_description"),
    ])
    return InlineKeyboardMarkup(rows), recent_tags


def priority_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 بالا", callback_data="priority_high")],
        [InlineKeyboardButton("🟠 متوسط", callback_data="priority_medium")],
        [InlineKeyboardButton("🟢 پایین", callback_data="priority_low")],
    ])


def deadline_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 امروز", callback_data="deadline_0"),
            InlineKeyboardButton("📅 فردا", callback_data="deadline_1"),
        ],
        [
            InlineKeyboardButton("📅 ۱ هفته", callback_data="deadline_7"),
            InlineKeyboardButton("📅 ۲ هفته", callback_data="deadline_14"),
        ],
        [
            InlineKeyboardButton("♾️ بدون زمان‌بندی", callback_data="deadline_none"),
            InlineKeyboardButton("✍️ تاریخ دقیق", callback_data="deadline_custom"),
        ],
    ])


def assignment_grid_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🙋‍♂️ خودم", callback_data="assign_self"),
            InlineKeyboardButton("👥 هم‌تیمی‌ها", callback_data="assign_team"),
        ],
        [
            InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="assign_search"),
            InlineKeyboardButton("⏭ بدون مسئول", callback_data="assign_none"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت", callback_data="step_back_tags"),
        ],
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
