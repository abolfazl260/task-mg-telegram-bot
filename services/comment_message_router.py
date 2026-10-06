"""Route Telegram task comments into the canonical task-comment repository."""

import logging

from telegram.ext import Application, MessageHandler, filters

from bot_context import get_current_bot_key
from services.comment_message_store import add_comment_message_async, get_comment_messages_async

logger = logging.getLogger(__name__)
_BOTS = {}


async def _handle_task_comment_message(update, context):
    if context.user_data.get("step") != "task_comment":
        return

    message = update.effective_message
    user = update.effective_user
    task_id = context.user_data.get("comment_task_id")
    if not message or not user or not task_id:
        return

    profile = context.bot_data.get("bot_config")
    bot_key = profile.key if profile else "default"
    _BOTS[bot_key] = context.bot

    from handlers import task as task_module

    try:
        task = await task_module.get_task_by_id_async(task_id)
        if not task or not await task_module._can_view_task(user.id, task):
            context.user_data.pop("comment_task_id", None)
            context.user_data.pop("step", None)
            await message.reply_text("تسک پیدا نشد یا دسترسی ندارید.")
            return

        ok = await add_comment_message_async(
            task_id,
            {"id": user.id, "full_name": user.full_name, "username": user.username or ""},
            message,
        )
        context.user_data.pop("comment_task_id", None)
        context.user_data.pop("step", None)
        await message.reply_text("✅ کامنت ثبت شد." if ok else "❌ خطا در ثبت کامنت.")
    except Exception:
        logger.exception(
            "Failed to save task comment task_id=%s user_id=%s message_id=%s",
            task_id,
            user.id,
            getattr(message, "message_id", None),
        )
        await message.reply_text("❌ خطا در ثبت کامنت. لطفاً دوباره تلاش کنید.")


async def _send_legacy_attachment(message, comment: dict) -> bool:
    file_id = comment.get("file_id")
    ctype = comment.get("type")
    if not file_id:
        return False

    caption = (
        f"{comment.get('author_name') or 'کاربر'}\n"
        f"🕐 {comment.get('created_at') or '—'}\n"
        f"{comment.get('caption') or comment.get('text') or comment.get('file_name') or ''}"
    )[:1024]
    try:
        if ctype == "photo":
            await message.reply_photo(file_id, caption=caption)
        elif ctype == "voice":
            await message.reply_voice(file_id, caption=caption)
        elif ctype == "audio":
            await message.reply_audio(file_id, caption=caption)
        elif ctype == "video":
            await message.reply_video(file_id, caption=caption)
        elif ctype == "animation":
            await message.reply_animation(file_id, caption=caption)
        elif ctype == "sticker":
            await message.reply_sticker(file_id)
        elif ctype == "document":
            await message.reply_document(file_id, caption=caption)
        else:
            return False
        return True
    except Exception:
        logger.exception(
            "task_comment_attachment_send_failed task_id=%s content_type=%s operation=send_attachment",
            comment.get("task_id"),
            ctype,
        )
        return False


async def _patched_send_comment_attachments(message, task_id: str):
    """Replay Telegram-origin comments and preserve legacy file-id attachments."""
    comments = await get_comment_messages_async(task_id)
    if not comments:
        return

    profile_key = get_current_bot_key() or "default"
    target_chat_id = message.chat_id
    announced = False

    for index, comment in enumerate(comments, start=1):
        chat_id = comment.get("chat_id")
        message_id = comment.get("message_id")
        if chat_id and message_id:
            if not announced:
                active_bot = _BOTS.get(profile_key)
                if active_bot is not None:
                    await active_bot.send_message(chat_id=target_chat_id, text="💬 جزئیات کامنت‌ها:")
                announced = True

            source_bot = _BOTS.get(comment.get("bot_key")) or _BOTS.get(profile_key)
            if source_bot is None:
                logger.warning(
                    "No active bot instance available for comment replay bot_key=%s task_id=%s",
                    comment.get("bot_key"),
                    task_id,
                )
                continue

            source_chat_id = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
            try:
                await source_bot.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message_id,
                )
                continue
            except Exception:
                logger.warning(
                    "copy_message failed for task_id=%s chat_id=%s message_id=%s; trying forward_message",
                    task_id,
                    chat_id,
                    message_id,
                    exc_info=True,
                )

            try:
                await source_bot.forward_message(
                    chat_id=target_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message_id,
                )
            except Exception:
                logger.exception(
                    "Could not replay stored Telegram comment task_id=%s chat_id=%s message_id=%s",
                    task_id,
                    chat_id,
                    message_id,
                )
                await source_bot.send_message(
                    chat_id=target_chat_id,
                    text=(
                        f"⚠️ کامنت شماره {index} قابل فراخوانی نیست.\n"
                        f"🕐 {comment.get('created_at') or '—'}\n"
                        f"👤 {comment.get('author_name') or 'کاربر'}"
                    ),
                )
            continue

        await _send_legacy_attachment(message, comment)


def _install():
    from handlers import task as task_module

    # The canonical reader/formatter now live in task_service/comment_message_store.
    # Only Telegram-specific replay still needs a channel adapter.
    task_module._send_comment_attachments = _patched_send_comment_attachments

    if getattr(Application, "_task_comment_message_router_patch", False):
        return

    original_add_handler = Application.add_handler

    def patched_add_handler(self, handler, group=0):
        marker = "_task_comment_message_router_installed"
        if not self.bot_data.get(marker):
            original_add_handler(
                self,
                MessageHandler(filters.ALL & ~filters.COMMAND, _handle_task_comment_message),
                group=-3,
            )
            self.bot_data[marker] = True
        return original_add_handler(self, handler, group=group)

    Application.add_handler = patched_add_handler
    Application._task_comment_message_router_patch = True


_install()
