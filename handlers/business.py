import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import SECRETARY_AUTO_REPLY_ENABLED, SECRETARY_AUTO_REPLY_TEXT
from services.business_service import (
    get_business_connection,
    record_business_message,
    record_deleted_business_messages,
    upsert_business_connection,
)

logger = logging.getLogger(__name__)


def _business_help(connection):
    status = "فعال" if connection.get("is_enabled") else "غیرفعال"
    can_reply = "دارد" if connection.get("can_reply") else "ندارد"
    return (
        "🤝 حالت Secretary برای این بات ثبت شد.\n\n"
        f"وضعیت اتصال: {status}\n"
        f"اجازه پاسخ‌گویی از طرف شما: {can_reply}\n\n"
        "از مسیر Manage Bot در چت‌های مدیریت‌شده می‌توانید دسترسی‌ها را تغییر دهید."
    )


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = update.business_connection
    if not connection:
        return

    saved = upsert_business_connection(connection)
    logger.info(
        "business_connection id=%s user_id=%s is_enabled=%s can_reply=%s",
        connection.id,
        connection.user.id,
        connection.is_enabled,
        connection.can_reply,
    )

    await context.bot.send_message(
        chat_id=connection.user_chat_id,
        text=_business_help(saved),
    )


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.business_message
    if not message:
        return

    entry = record_business_message(message, event_type="business_message")
    logger.info(
        "business_message connection_id=%s chat_id=%s message_id=%s",
        entry["business_connection_id"],
        entry["chat_id"],
        entry["message_id"],
    )

    connection = get_business_connection(message.business_connection_id)
    if not connection or not connection.get("can_reply") or not connection.get("is_enabled"):
        return

    text = (message.text or "").strip()
    if text == "/secretary_status":
        await context.bot.send_message(
            chat_id=message.chat_id,
            text="✅ Secretary Mode فعال است و بات می‌تواند پیام‌های این چت را پردازش کند.",
            business_connection_id=message.business_connection_id,
        )
    elif SECRETARY_AUTO_REPLY_ENABLED and text:
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=SECRETARY_AUTO_REPLY_TEXT,
            business_connection_id=message.business_connection_id,
        )


async def handle_edited_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.edited_business_message
    if not message:
        return
    entry = record_business_message(message, event_type="edited_business_message")
    logger.info(
        "edited_business_message connection_id=%s chat_id=%s message_id=%s",
        entry["business_connection_id"],
        entry["chat_id"],
        entry["message_id"],
    )


async def handle_deleted_business_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deleted = update.deleted_business_messages
    if not deleted:
        return
    entry = record_deleted_business_messages(deleted)
    logger.info(
        "deleted_business_messages connection_id=%s chat_id=%s message_ids=%s",
        entry["business_connection_id"],
        entry["chat_id"],
        entry["message_ids"],
    )
