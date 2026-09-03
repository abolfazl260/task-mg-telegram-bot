"""Telegram voice-message input with streamed Rich AI task drafts."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from html import escape
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from config import VOICE_MAX_DURATION_SECONDS, VOICE_MAX_SIZE_MB
from handlers.ai import ai_command
from services.speech_to_text import (
    SpeechToTextConfigurationError,
    SpeechToTextError,
    SpeechToTextRequestError,
    get_speech_to_text_service,
)
from services.task_intelligence import parse_task_request_smart

logger = logging.getLogger(__name__)

_VOICE_PROCESSING_SEMAPHORE = asyncio.Semaphore(3)


def _rich_draft_html(title: str, body: str, *, thinking: bool = False) -> str:
    thinking_block = "<tg-thinking>در حال آماده‌سازی...</tg-thinking>" if thinking else ""
    return (
        f"<p><b>{escape(title)}</b></p>"
        f"{thinking_block}"
        f"<p>{escape(body)}</p>"
    )


def _rich_ai_draft_html(draft: dict) -> str:
    missing = "—"
    if draft.get("action") == "CREATE_HABIT":
        repeat = {
            "daily": "روزانه",
            "weekly": "هفتگی",
            "monthly": "ماهانه",
        }.get(draft.get("repeat_type"), missing)
        return (
            "<p><b>🤖 پیش‌نویس عادت پیشنهادی هوش مصنوعی</b></p>"
            "<p>بر اساس وویس شما این پیش‌نویس آماده شده است:</p>"
            "<p>━━━━━━━━━━━━━━━━</p>"
            f"<p>🌱 <b>عنوان</b><br>{escape(str(draft.get('title') or missing))}</p>"
            f"<p>🔁 <b>تکرار</b><br>{escape(repeat)}</p>"
            f"<p>🎯 <b>هدف</b><br>{escape(str(draft.get('target') or missing))}</p>"
            f"<p>⏰ <b>یادآوری</b><br>{escape(str(draft.get('reminder_time') or missing))}</p>"
            f"<p>📂 <b>دسته‌بندی</b><br>{escape(str(draft.get('category') or missing))}</p>"
            f"<p>🏷 <b>تگ</b><br>{escape(str(draft.get('tags') or missing))}</p>"
            f"<p>📝 <b>توضیح</b><br>{escape(str(draft.get('description') or missing))}</p>"
            "<p>━━━━━━━━━━━━━━━━</p>"
            "<p><b>آیا این پیش‌نویس مورد تأیید شماست؟</b></p>"
            '<tg-button-row align="center">'
            '<tg-button type="callback_data" style="success" data="ai_habit_create">🌱 افزودن به عادت‌ها</tg-button>'
            '<tg-button type="callback_data" style="link" data="ai_habit_cancel">❌ لغو</tg-button>'
            "</tg-button-row>"
        )

    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(
        draft.get("priority"), "🟢 پایین"
    )
    return (
        "<p><b>🤖 پیش‌نویس تسک پیشنهادی هوش مصنوعی</b></p>"
        "<p>بر اساس وویس شما این پیش‌نویس آماده شده است:</p>"
        "<p>━━━━━━━━━━━━━━━━</p>"
        f"<p>📌 <b>عنوان</b><br>{escape(str(draft.get('title') or missing))}</p>"
        f"<p>🗓 <b>موعد</b><br>{escape(str(draft.get('deadline') or missing))}</p>"
        f"<p>🎯 <b>اولویت</b><br>{escape(priority)}</p>"
        f"<p>📂 <b>دسته‌بندی</b><br>{escape(str(draft.get('category') or missing))}</p>"
        f"<p>🏷 <b>تگ</b><br>{escape(str(draft.get('tags') or missing))}</p>"
        f"<p>📝 <b>توضیحات</b><br>{escape(str(draft.get('description') or missing))}</p>"
        "<p>━━━━━━━━━━━━━━━━</p>"
        "<p><b>آیا این پیش‌نویس مورد تأیید شماست؟</b></p>"
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="success" data="ai_task_create">✅ ایجاد تسک</tg-button>'
        '<tg-button type="callback_data" style="link" data="ai_task_cancel">❌ لغو</tg-button>'
        "</tg-button-row>"
    )


async def _stream_rich_draft(bot, chat_id: int, draft_id: int, html: str, *, can_stop: bool = False) -> None:
    """Best-effort Rich live preview. Voice processing must still work if Rich drafts fail."""
    try:
        await bot._post(
            "sendRichMessageDraft",
            data={
                "chat_id": chat_id,
                "draft_id": draft_id,
                "rich_message": {"html": html, "is_rtl": True},
                "can_stop": can_stop,
            },
        )
    except Exception as exc:
        logger.debug("voice_rich_draft_failed chat_id=%s error=%s", chat_id, exc)


async def _send_rich_final(bot, chat_id: int, html: str):
    """Persist the final AI draft as a Rich Message."""
    return await bot._post(
        "sendRichMessage",
        data={
            "chat_id": chat_id,
            "rich_message": {"html": html, "is_rtl": True},
        },
    )


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download voice, transcribe it, stream AI progress, then suggest a task draft."""
    message = update.message
    voice = message.voice if message else None
    if not message or not voice:
        return

    if voice.duration and voice.duration > VOICE_MAX_DURATION_SECONDS:
        await message.reply_text(
            f"⚠️ وویس بیش از حد مجاز طولانی است. حداکثر زمان مجاز {VOICE_MAX_DURATION_SECONDS // 60} دقیقه است."
        )
        return

    max_size = VOICE_MAX_SIZE_MB * 1024 * 1024
    if voice.file_size and voice.file_size > max_size:
        await message.reply_text(
            f"⚠️ حجم وویس بیش از حد مجاز است. حداکثر حجم {VOICE_MAX_SIZE_MB} مگابایت است."
        )
        return

    chat_id = message.chat_id
    draft_id = max(1, int(time.time_ns() % 2_000_000_000))
    temp_path: Path | None = None

    await _stream_rich_draft(
        context.bot,
        chat_id,
        draft_id,
        _rich_draft_html("🎙️ پردازش وویس", "در حال دریافت و تبدیل وویس به متن...", thinking=True),
        can_stop=True,
    )

    try:
        async with _VOICE_PROCESSING_SEMAPHORE:
            try:
                telegram_file = await voice.get_file()
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                    temp_path = Path(temp_file.name)
                await telegram_file.download_to_drive(custom_path=temp_path)
            except Exception as exc:
                logger.warning(
                    "voice_download_failed user_id=%s error=%s",
                    update.effective_user.id if update.effective_user else None,
                    exc,
                )
                raise SpeechToTextRequestError("دانلود فایل صوتی ناموفق بود.") from exc

            if not temp_path.is_file() or temp_path.stat().st_size == 0:
                raise SpeechToTextRequestError("فایل صوتی خالی یا خراب است.")
            if temp_path.stat().st_size > max_size:
                raise SpeechToTextRequestError("حجم فایل صوتی بیش از حد مجاز است.")

            await _stream_rich_draft(
                context.bot,
                chat_id,
                draft_id,
                _rich_draft_html("🎙️ پردازش وویس", "وویس دریافت شد؛ در حال تبدیل صدا به متن...", thinking=True),
                can_stop=True,
            )

            service = get_speech_to_text_service()
            text = await asyncio.to_thread(service.transcribe, temp_path)
            if not text.strip():
                raise SpeechToTextRequestError("متنی از فایل صوتی قابل تشخیص نبود.")

            await _stream_rich_draft(
                context.bot,
                chat_id,
                draft_id,
                _rich_draft_html("🧠 ساخت پیش‌نویس", "متن وویس دریافت شد؛ هوش مصنوعی در حال ساخت پیش‌نویس تسک است...", thinking=True),
                can_stop=True,
            )

            try:
                draft = await asyncio.to_thread(
                    parse_task_request_smart,
                    update.effective_user.id,
                    text,
                )
            except Exception:
                # Preserve the existing AI pipeline for non-task requests or
                # cases where structured parsing cannot be used here.
                draft = None

            if isinstance(draft, dict) and draft.get("action") in {"CREATE_TASK", "CREATE_HABIT"}:
                context.user_data["ai_request_draft"] = draft
                await _stream_rich_draft(
                    context.bot,
                    chat_id,
                    draft_id,
                    _rich_ai_draft_html(draft),
                )
                await _send_rich_final(context.bot, chat_id, _rich_ai_draft_html(draft))
                return

            # Non-task voice requests keep the existing AI behavior.
            await _stream_rich_draft(
                context.bot,
                chat_id,
                draft_id,
                _rich_draft_html("🤖 دستیار هوشمند", "درخواست شما شناسایی شد؛ در حال آماده‌سازی پاسخ...", thinking=True),
                can_stop=True,
            )
            original_args = getattr(context, "args", None)
            context.args = [text]
            try:
                await ai_command(update, context)
            finally:
                context.args = original_args

    except SpeechToTextConfigurationError:
        await _replace_status(message, "⚠️ قابلیت تبدیل وویس به متن در حال حاضر فعال نیست.")
    except SpeechToTextRequestError as exc:
        await _replace_status(message, f"⚠️ {exc}")
    except SpeechToTextError:
        await _replace_status(message, "⚠️ پردازش وویس ناموفق بود. لطفاً دوباره تلاش کنید.")
    except Exception:
        logger.exception(
            "voice_processing_failed user_id=%s",
            update.effective_user.id if update.effective_user else None,
        )
        await _replace_status(message, "⚠️ پردازش وویس ناموفق بود. لطفاً دوباره تلاش کنید.")
    finally:
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


async def _replace_status(message, text: str) -> None:
    # Rich draft is ephemeral; errors therefore become a normal persistent message.
    try:
        await message.reply_text(text)
    except Exception:
        pass
