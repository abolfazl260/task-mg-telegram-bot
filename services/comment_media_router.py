"""Route Telegram media messages into the active task-comment flow."""

import logging
from weakref import WeakKeyDictionary

from telegram.ext import Application, MessageHandler, filters

logger = logging.getLogger(__name__)


async def _handle_comment_media(update, context):
    if context.user_data.get("step") != "task_comment":
        return

    message = update.effective_message
    if not message or message.text:
        return

    from handlers import task as task_module

    task_id = context.user_data.get("comment_task_id")
    if not task_id:
        return

    try:
        task = await task_module.get_task_by_id_async(task_id)
        if not task or not await task_module._can_view_task(update.effective_user.id, task):
            context.user_data.pop("comment_task_id", None)
            context.user_data.pop("comment_attachment_count", None)
            context.user_data.pop("step", None)
            await message.reply_text("تسک پیدا نشد یا دسترسی ندارید.")
            return

        content = task_module._extract_comment_content(message)
        if not content:
            await message.reply_text("❌ این نوع فایل پشتیبانی نمی‌شود.")
            return

        user = update.effective_user
        ok = await task_module.add_task_comment_async(
            task_id,
            {"id": user.id, "full_name": user.full_name, "username": user.username or ""},
            content,
        )
        if not ok:
            await message.reply_text("❌ خطا در ثبت کامنت.")
            return

        count = int(context.user_data.get("comment_attachment_count", 0)) + 1
        context.user_data["comment_attachment_count"] = count
        await message.reply_text(
            f"✅ مورد {count} ثبت شد.\n"
            "می‌توانید فایل، عکس، صدا، ویدیو یا متن دیگری بفرستید.\n"
            "برای پایان ارسال، کلمه «تمام» را بفرستید."
        )
    except Exception:
        logger.exception("Failed to store comment media")
        await message.reply_text("❌ خطا در دریافت فایل. لطفاً دوباره تلاش کنید.")


_MEDIA_FILTER = (
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


_original_add_handler = Application.add_handler
_installed_applications = WeakKeyDictionary()


def _patched_add_handler(self, handler, group=0):
    # Application uses __slots__, so never attach arbitrary attributes to it.
    # WeakKeyDictionary lets us track installation without modifying Application.
    if not _installed_applications.get(self) and isinstance(handler, MessageHandler):
        _installed_applications[self] = True
        _original_add_handler(
            self,
            MessageHandler(_MEDIA_FILTER, _handle_comment_media),
            group=group - 1,
        )
    return _original_add_handler(self, handler, group)


if not getattr(Application.add_handler, "_task_comment_media_patch", False):
    _patched_add_handler._task_comment_media_patch = True
    Application.add_handler = _patched_add_handler
