"""Route task comments through durable Telegram message references.

The task-comment DB stores only the original Telegram chat/message reference,
never the binary media, file_id, or a media-specific content JSON payload.
"""

import logging

from telegram.ext import Application, MessageHandler, filters

from services.comment_message_store import add_comment_message_async, get_comment_messages_async

logger = logging.getLogger(__name__)


async def _handle_comment_message(update, context):
    if context.user_data.get("step") != "task_comment":
        return

    message = update.effective_message
    user = update.effective_user
    task_id = context.user_data.get("comment_task_id")
    if not message or not user or not task_id:
        return

    from handlers import task as task_module

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
    if ok:
        await message.reply_text("✅ کامنت ثبت شد.")
    else:
        await message.reply_text("❌ خطا در ثبت کامنت.")


async def _patched_handle_comment_input(update, context):
    if context.user_data.get("step") != "task_comment":
        return False

    message = update.effective_message
    user = update.effective_user
    task_id = context.user_data.get("comment_task_id")
    if not message or not user or not task_id:
        return True

    from handlers import task as task_module

    task = await task_module.get_task_by_id_async(task_id)
    if not task or not await task_module._can_view_task(user.id, task):
        context.user_data.pop("comment_task_id", None)
        context.user_data.pop("step", None)
        await message.reply_text("تسک پیدا نشد یا دسترسی ندارید.")
        return True

    ok = await add_comment_message_async(
        task_id,
        {"id": user.id, "full_name": user.full_name, "username": user.username or ""},
        message,
    )
    context.user_data.pop("comment_task_id", None)
    context.user_data.pop("step", None)
    await message.reply_text("✅ کامنت ثبت شد." if ok else "❌ خطا در ثبت کامنت.")
    return True


async def _patched_get_task_comments_async(task_id):
    rows = await get_comment_messages_async(task_id)
    return [
        {
            "author_id": str(row.get("author_id") or ""),
            "author_name": row.get("author_name") or "کاربر",
            "author_username": row.get("author_username") or "",
            "created_at": row.get("created_at") or "",
            "chat_id": str(row.get("chat_id") or ""),
            "message_id": int(row.get("message_id") or 0),
        }
        for row in rows
    ]


async def _patched_comments_markdown(task_id: str) -> str:
    comments = await _patched_get_task_comments_async(task_id)
    if not comments:
        return "💬 هنوز کامنتی برای این تسک ثبت نشده است."
    lines = ["💬 کامنت‌ها", ""]
    for i, comment in enumerate(comments, start=1):
        author = comment.get("author_name") or "کاربر"
        username = f" (@{comment.get('author_username')})" if comment.get("author_username") else ""
        lines.append(f"{i}. 💬 پیام تلگرام — {author}{username}")
        lines.append(f"   🕐 {comment.get('created_at') or '—'}")
        lines.append("")
    return "\n".join(lines).strip()


async def _patched_send_comment_attachments(message, task_id: str):
    for comment in await _patched_get_task_comments_async(task_id):
        chat_id = comment.get("chat_id")
        message_id = comment.get("message_id")
        if not chat_id or not message_id:
            continue
        try:
            await message.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
                message_id=message_id,
            )
        except Exception:
            logger.exception(
                "Could not copy stored Telegram comment message chat_id=%s message_id=%s",
                chat_id,
                message_id,
            )


def _install():
    from handlers import task as task_module

    task_module.handle_comment_input = _patched_handle_comment_input
    task_module.get_task_comments_async = _patched_get_task_comments_async
    task_module._comments_markdown = _patched_comments_markdown
    task_module._send_comment_attachments = _patched_send_comment_attachments

    if getattr(Application, "_task_comment_message_router_installed", False):
        return

    original_add_handler = Application.add_handler

    media_filter = (
        filters.PHOTO
        | filters.Document.ALL
        | filters.VIDEO
        | filters.AUDIO
        | filters.VOICE
        | filters.ANIMATION
        | filters.Sticker.ALL
        | filters.CONTACT
        | filters.LOCATION
    )

    def patched_add_handler(self, handler, group=0):
        if not getattr(self, "_task_comment_message_router_installed", False) and isinstance(handler, MessageHandler):
            self._task_comment_message_router_installed = True
            original_add_handler(self, MessageHandler(media_filter, _handle_comment_message), group=group)
        return original_add_handler(self, handler, group=group)

    Application.add_handler = patched_add_handler
    Application._task_comment_message_router_installed = True


_install()
