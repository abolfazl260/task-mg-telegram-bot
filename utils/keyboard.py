from datetime import datetime, timedelta
import logging

import jdatetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.database import get_db
from bot_context import get_current_bot_key

logger = logging.getLogger(__name__)
MAX_TAG_LENGTH = 30


async def recent_tag_keyboard(user_id: int, limit: int = 3):
    """Build tag suggestions from this user's tasks for the current bot only."""
    db = await get_db()
    bot_key = get_current_bot_key() or "default"
    normalized_user_id = str(user_id)
    try:
        async with db.conn.execute(
            """
            SELECT tags FROM tasks
            WHERE bot_key = ? AND user_id = ? AND tags IS NOT NULL AND TRIM(tags) <> ''
            ORDER BY created_at DESC LIMIT 50
            """, (bot_key, normalized_user_id)
        ) as cursor:
            rows = await cursor.fetchall()
    except Exception:
        logger.exception("tag_suggestions query failed bot_key=%s user_id=%s", bot_key, normalized_user_id)
        raise
    recent_tags, seen = [], set()
    for row in rows:
        for tag in str(row[0] or "").replace("\n", ",").replace("،", ",").split(","):
            tag = tag.strip().lstrip("#")[:MAX_TAG_LENGTH]
            if not tag or tag.casefold() in seen:
                continue
            seen.add(tag.casefold())
            recent_tags.append(tag)
            if len(recent_tags) >= limit:
                break
        if len(recent_tags) >= limit:
            break
    rows = []
    for index in range(0, len(recent_tags), 2):
        rows.append([InlineKeyboardButton(f"🏷 {tag}", callback_data=f"tag_pick_{index + offset}") for offset, tag in enumerate(recent_tags[index:index + 2])])
    rows.append([InlineKeyboardButton("➕ تایپ تگ جدید", callback_data="tag_new")])
    rows.append([InlineKeyboardButton("⏭ بدون تگ (رد شدن)", callback_data="tag_none"), InlineKeyboardButton("🔙 مرحله قبل", callback_data="step_back_category")])
    return InlineKeyboardMarkup(rows), recent_tags


def priority_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 بالا", callback_data="priority_high")],
        [InlineKeyboardButton("🟠 متوسط", callback_data="priority_medium")],
        [InlineKeyboardButton("🟢 پایین", callback_data="priority_low")],
    ])


def deadline_keyboard():
    today = datetime.now().date()
    rows = []
    def date_label(days: int) -> str:
        target = today + timedelta(days=days)
        jalali = jdatetime.date.fromgregorian(date=target).strftime("%m/%d")
        prefix = "امروز" if days == 0 else "فردا" if days == 1 else f"+{days} روز"
        return f"{prefix} — {jalali}"
    rows.append([InlineKeyboardButton(date_label(0), callback_data="deadline_0"), InlineKeyboardButton(date_label(1), callback_data="deadline_1")])
    for start in (2, 4, 6):
        rows.append([InlineKeyboardButton(date_label(start), callback_data=f"deadline_{start}"), InlineKeyboardButton(date_label(start + 1), callback_data=f"deadline_{start + 1}")])
    rows.append([InlineKeyboardButton("🕐 انتخاب تاریخ و زمان", callback_data="deadline_custom")])
    rows.append([InlineKeyboardButton("⏭ بدون زمان‌بندی", callback_data="deadline_none")])
    rows.append([InlineKeyboardButton("🔙 مرحله قبل", callback_data="step_back_priority")])
    return InlineKeyboardMarkup(rows)


def assignment_grid_keyboard(user_id: int | None = None):
    self_callback = f"assign_self_{user_id}" if user_id is not None else "assign_self"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🙋‍♂️ خودم", callback_data=self_callback), InlineKeyboardButton("👥 هم‌تیمی‌ها", callback_data="assign_teams")],
        [InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="assign_search"), InlineKeyboardButton("⏭ بدون مسئول", callback_data="assign_none")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="step_back_tags")],
    ])


def _task_option_enabled(bot_profile, name: str) -> bool:
    if bot_profile is None:
        return True
    options = (getattr(bot_profile, "settings", {}) or {}).get("task_options", {}) or {}
    return bool(options.get(name, True))


def task_action_keyboard(task_id: str, current_status: str = "pending", bot_profile=None, comment_count: int = 0):
    """Compact task-card actions filtered by the active BotProfile capabilities."""
    labels = bot_profile.workflow.get("actions", {}) if bot_profile is not None else {}
    buttons = []
    status_row = []
    if current_status == "pending":
        status_row.append(InlineKeyboardButton(labels.get("start", "🚀 شروع"), callback_data=f"start_{task_id}"))
    if current_status in ("pending", "in_progress"):
        status_row.extend([
            InlineKeyboardButton(labels.get("done", "✅ انجام شد"), callback_data=f"done_{task_id}"),
            InlineKeyboardButton(labels.get("cancel", "❌ لغو"), callback_data=f"cancel_{task_id}"),
        ])
    if current_status == "in_progress":
        buttons.append([InlineKeyboardButton(labels.get("pending", "⏸ بازگشت به انتظار"), callback_data=f"pending_{task_id}")])
    if status_row:
        buttons.append(status_row)

    detail_buttons = [InlineKeyboardButton(labels.get("details", "🔍 جزئیات و تاریخچه"), callback_data=f"task_details_{task_id}")]
    if _task_option_enabled(bot_profile, "allow_comments"):
        detail_buttons.insert(0, InlineKeyboardButton(f"💬 کامنت ({comment_count})", callback_data=f"comment_add_{task_id}"))
    buttons.append(detail_buttons)

    if _task_option_enabled(bot_profile, "allow_assignment"):
        buttons.append([
            InlineKeyboardButton(labels.get("owner", "👤 تغییر مسئول"), callback_data=f"owner_{task_id}"),
            InlineKeyboardButton(labels.get("take", "🙋‍♂️ برعهده گرفتن"), callback_data=f"take_{task_id}"),
        ])
    return InlineKeyboardMarkup(buttons)
