"""Speech-to-text integrations used by voice message handlers."""

from __future__ import annotations

import json
import logging
import mimetypes
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from config import STT_API_KEY, STT_API_URL, STT_LANGUAGE, STT_MODEL, STT_PROVIDER

logger = logging.getLogger(__name__)


class SpeechToTextError(RuntimeError):
    """Base error for speech-to-text failures."""


class SpeechToTextConfigurationError(SpeechToTextError):
    """Raised when the configured speech-to-text provider is unavailable."""


class SpeechToTextRequestError(SpeechToTextError):
    """Raised when the speech-to-text provider cannot process the audio."""


class SpeechToTextService(ABC):
    """Provider-neutral contract for converting an audio file into text."""

    @abstractmethod
    def transcribe(self, audio_path: str | Path) -> str:
        """Return the recognized text or raise SpeechToTextError."""


class GroqSpeechToTextService(SpeechToTextService):
    """Groq Whisper-compatible speech-to-text provider."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        language: str | None = None,
    ) -> None:
        self.api_key = api_key or STT_API_KEY
        self.api_url = api_url or STT_API_URL
        self.model = model or STT_MODEL
        self.language = STT_LANGUAGE if language is None else language.strip()

    def transcribe(self, audio_path: str | Path) -> str:
        if not self.api_key:
            raise SpeechToTextConfigurationError("STT_API_KEY تنظیم نشده است.")

        path = Path(audio_path)
        if not path.is_file():
            raise SpeechToTextRequestError("فایل صوتی قابل دسترسی نیست.")

        body, content_type = _build_multipart_body(path, self.model, self.language)
        request = urllib.request.Request(
            self.api_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
                "User-Agent": "task-mg-telegram-bot/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:500]
            logger.warning("stt_http_error status=%s detail=%s", exc.code, detail)
            raise SpeechToTextRequestError("سرویس تبدیل صدا به متن پاسخ مناسبی نداد.") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("stt_request_failed error=%s", exc)
            raise SpeechToTextRequestError("ارتباط با سرویس تبدیل صدا به متن برقرار نشد.") from exc

        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise SpeechToTextRequestError("متنی از فایل صوتی قابل تشخیص نبود.")
        return text.strip()


def _build_multipart_body(
    audio_path: Path, model: str, language: str = ""
) -> tuple[bytes, str]:
    """Build the multipart request without adding a third-party HTTP dependency."""
    boundary = "----taskbot-stt-boundary"
    content_type = f"multipart/form-data; boundary={boundary}"
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    audio = audio_path.read_bytes()

    fields = [("model", model)]
    if language:
        fields.append(("language", language))

    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{audio_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            audio,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), content_type


def get_speech_to_text_service() -> SpeechToTextService:
    """Return the configured provider behind the provider-neutral interface."""
    provider = STT_PROVIDER.strip().lower()
    if provider == "groq":
        return GroqSpeechToTextService()
    raise SpeechToTextConfigurationError(f"ارائه‌دهنده STT ناشناخته است: {provider}")
