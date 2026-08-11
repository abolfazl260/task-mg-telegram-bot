from datetime import datetime, timedelta

import jdatetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.database import get_db
from bot_context import get_current_bot_key


async def recent_tag_keyboard(user_id: int, limit: int = 3):
    """Build up to three unique tags from the user's latest tagged tasks."""
    db = await get_db()
    bot_key = get_current_bot_key() or "default"
    async with db.conn.execute(
        """
        SELECT tags
        FROM tasks
        WHERE bot_key = ?
          AND user_id = ?
          AND tags IS NOT NULL
          AND TRIM(tags) <> ''
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (bot_key, str(user_id)),
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
        row_buttons = []
        for offset, tag in enumerate(recent_tags[index:index + 2]):
            row_buttons.append(
                InlineKeyboardButton(
                    f"🏷 {tag}",
                    callback_data=f"tag_pick_{index + offset}",
                )
            )
        rows.append(row_buttons)

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
    """Show quick deadline choices for today and the next seven days."""
    today = datetime.now().date()
    rows = []

    def date_label(days: int) -> str:
        target = today + timedelta(days=days)
        jalali = jdatetime.date.fromgregorian(date=target).strftime("%m/%d")
        if days == 0:
            prefix = "امروز"
        elif days == 1:
            prefix = "فردا"
        else:
            prefix = f"+{days} روز"
        return f"{prefix} — {jalali}"

    rows.append([
        InlineKeyboardButton(date_label(0), callback_data="deadline_0"),
        InlineKeyboardButton(date_label(1), callback_data="deadline_1"),
    ])
    for start in (2, 4, 6):
        rows.append([
            InlineKeyboardButton(date_label(start), callback_data=f"deadline_{start}"),
            InlineKeyboardButton(date_label(start + 1), callback_data=f"deadline_{start + 1}"),
        ])
    rows.append([InlineKeyboardButton("🕐 انتخاب تاریخ و زمان", callback_data="deadline_custom")])
    rows.append([InlineKeyboardButton("⏭ بدون زمان‌بندی", callback_data="deadline_none")])
    rows.append([InlineKeyboardButton("🔙 مرحله قبل", callback_data="step_back_priority")])
    return InlineKeyboardMarkup(rows)


def assignment_grid_keyboard(user_id: int | None = None):
    """Keyboard for choosing the task assignee."""
    self_callback = f"assign_self_{user_id}" if user_id is not None else "assign_self"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🙋‍♂️ خودم", callback_data=self_callback),
            InlineKeyboardButton("👥 هم‌تیمی‌ها", callback_data="assign_teams"),
        ],
        [
            InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="assign_search"),
            InlineKeyboardButton("⏭ بدون مسئول", callback_data="assign_none"),
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="step_back_tags")],
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
