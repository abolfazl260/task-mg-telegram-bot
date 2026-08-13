"""Telegram voice-message input adapter for the existing AI pipeline."""

from __future__ import annotations

import asyncio
import logging
import tempfile
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

logger = logging.getLogger(__name__)

# Prevent a burst of voice messages from creating too many simultaneous
# blocking STT/AI operations and consuming excessive threads/resources.
_VOICE_PROCESSING_SEMAPHORE = asyncio.Semaphore(3)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download a Telegram voice message, transcribe it, then reuse ai_command."""
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

    status_message = await message.reply_text("🎤 در حال پردازش وویس...")
    temp_path: Path | None = None
    try:
        # Bound the complete voice-processing pipeline so bursts of voice
        # messages cannot create an unbounded number of blocking operations.
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

            service = get_speech_to_text_service()
            text = await asyncio.to_thread(service.transcribe, temp_path)
            if not text.strip():
                raise SpeechToTextRequestError("متنی از فایل صوتی قابل تشخیص نبود.")

            await status_message.delete()

            # ai_command is the existing text-input pipeline. Passing the full
            # transcription as one argument preserves punctuation and spacing.
            original_args = getattr(context, "args", None)
            context.args = [text]
            try:
                await ai_command(update, context)
            finally:
                context.args = original_args

    except SpeechToTextConfigurationError:
        await _replace_status(status_message, "⚠️ قابلیت تبدیل وویس به متن در حال حاضر فعال نیست.")
    except SpeechToTextRequestError as exc:
        await _replace_status(status_message, f"⚠️ {exc}")
    except SpeechToTextError:
        await _replace_status(status_message, "⚠️ پردازش وویس ناموفق بود. لطفاً دوباره تلاش کنید.")
    except Exception:
        logger.exception(
            "voice_processing_failed user_id=%s",
            update.effective_user.id if update.effective_user else None,
        )
        await _replace_status(status_message, "⚠️ پردازش وویس ناموفق بود. لطفاً دوباره تلاش کنید.")
    finally:
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


async def _replace_status(status_message, text: str) -> None:
    try:
        await status_message.edit_text(text)
    except Exception:
        try:
            await status_message.reply_text(text)
        except Exception:
            pass
