"""Route task comments through one durable Telegram-message reference flow."""

import logging

from telegram.ext import Application, MessageHandler, filters

from services.comment_message_store import add_comment_message_async, get_comment_messages_async

logger = logging.getLogger(__name__)


async def _handle_task_comment_message(update, context):
    if context.user_data.get("step") != "task_comment":
        return

    message = update.effective_message
    user = update.effective_user
    task_id = context.user_data.get("comment_task_id")
    if not message or not user or not task_id:
        return

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


async def _patched_send_comment_attachments(bot, target_chat_id, task_id: str):
    """Replay every original Telegram comment message in chronological order."""
    comments = await _patched_get_task_comments_async(task_id)
    if not comments:
        return

    await bot.send_message(chat_id=target_chat_id, text="💬 جزئیات کامنت‌ها:")

    for index, comment in enumerate(comments, start=1):
        chat_id = comment.get("chat_id")
        message_id = comment.get("message_id")
        if not chat_id or not message_id:
            logger.warning("Skipping comment without Telegram reference task_id=%s index=%s", task_id, index)
            continue

        source_chat_id = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
        try:
            await bot.copy_message(
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
            await bot.forward_message(
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
            await bot.send_message(
                chat_id=target_chat_id,
                text=(
                    f"⚠️ کامنت شماره {index} قابل فراخوانی نیست.\n"
                    f"🕐 {comment.get('created_at') or '—'}\n"
                    f"👤 {comment.get('author_name') or 'کاربر'}"
                ),
            )


def _install():
    from handlers import task as task_module

    task_module.get_task_comments_async = _patched_get_task_comments_async
    task_module._comments_markdown = _patched_comments_markdown

    async def _send_from_task_handler(message, task_id):
        await _patched_send_comment_attachments(message.get_bot(), message.chat_id, task_id)

    task_module._send_comment_attachments = _send_from_task_handler

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
