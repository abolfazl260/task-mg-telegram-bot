from types import SimpleNamespace

import pytest

from handlers import voice as voice_handler
from services.speech_to_text import SpeechToTextRequestError


class FakeStatusMessage:
    def __init__(self):
        self.deleted = False
        self.edits = []
        self.replies = []

    async def delete(self):
        self.deleted = True

    async def edit_text(self, text):
        self.edits.append(text)

    async def reply_text(self, text):
        self.replies.append(text)


class FakeMessage:
    def __init__(self, voice):
        self.voice = voice
        self.status = FakeStatusMessage()

    async def reply_text(self, text):
        self.status.replies.append(text)
        return self.status


class FakeTelegramFile:
    async def download_to_drive(self, custom_path):
        custom_path.write_bytes(b"valid audio")


class FakeVoice:
    duration = 30
    file_size = 100

    async def get_file(self):
        return FakeTelegramFile()


@pytest.fixture
def update_and_context():
    message = FakeMessage(FakeVoice())
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=123))
    context = SimpleNamespace(args=[])
    return update, context, message


@pytest.mark.asyncio
async def test_voice_message_is_received_and_transcribed(monkeypatch, update_and_context):
    update, context, message = update_and_context
    calls = {}

    class FakeSTT:
        def transcribe(self, path):
            calls["path"] = path
            return "فردا ساعت ۹ جلسه با تیم فروش دارم"

    async def fake_ai_command(received_update, received_context):
        calls["text"] = received_context.args[0]

    monkeypatch.setattr(voice_handler, "get_speech_to_text_service", lambda: FakeSTT())
    monkeypatch.setattr(voice_handler, "ai_command", fake_ai_command)

    await voice_handler.handle_voice_message(update, context)

    assert calls["text"] == "فردا ساعت ۹ جلسه با تیم فروش دارم"
    assert calls["path"].exists() is False
    assert message.status.deleted is True
    assert context.args == []


@pytest.mark.asyncio
async def test_voice_download_failure_is_user_friendly(monkeypatch, update_and_context):
    update, context, message = update_and_context

    class BrokenTelegramFile:
        async def download_to_drive(self, custom_path):
            raise OSError("network failure")

    async def broken_get_file():
        return BrokenTelegramFile()

    update.message.voice.get_file = broken_get_file
    monkeypatch.setattr(
        voice_handler,
        "get_speech_to_text_service",
        lambda: pytest.fail("STT must not be called after download failure"),
    )

    await voice_handler.handle_voice_message(update, context)

    assert message.status.edits == ["⚠️ دانلود فایل صوتی ناموفق بود."]


@pytest.mark.asyncio
async def test_transcription_error_is_user_friendly(monkeypatch, update_and_context):
    update, context, message = update_and_context

    class FailingSTT:
        def transcribe(self, path):
            raise SpeechToTextRequestError("سرویس تبدیل صدا به متن پاسخ مناسبی نداد.")

    monkeypatch.setattr(voice_handler, "get_speech_to_text_service", lambda: FailingSTT())

    await voice_handler.handle_voice_message(update, context)

    assert message.status.edits == ["⚠️ سرویس تبدیل صدا به متن پاسخ مناسبی نداد."]
    assert context.args == []


@pytest.mark.asyncio
async def test_empty_transcription_is_rejected(monkeypatch, update_and_context):
    update, context, message = update_and_context

    class EmptySTT:
        def transcribe(self, path):
            return "   "

    monkeypatch.setattr(voice_handler, "get_speech_to_text_service", lambda: EmptySTT())

    await voice_handler.handle_voice_message(update, context)

    assert message.status.edits == ["⚠️ متنی از فایل صوتی قابل تشخیص نبود."]


@pytest.mark.asyncio
async def test_invalid_voice_size_is_rejected(monkeypatch, update_and_context):
    update, context, message = update_and_context
    message.voice.file_size = voice_handler.VOICE_MAX_SIZE_MB * 1024 * 1024 + 1
    called = False

    def fake_service():
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(voice_handler, "get_speech_to_text_service", fake_service)

    await voice_handler.handle_voice_message(update, context)

    assert called is False
    assert "حجم وویس بیش از حد مجاز" in message.status.replies[0]


@pytest.mark.asyncio
async def test_invalid_voice_duration_is_rejected(update_and_context):
    update, context, message = update_and_context
    message.voice.duration = voice_handler.VOICE_MAX_DURATION_SECONDS + 1

    await voice_handler.handle_voice_message(update, context)

    assert "وویس بیش از حد مجاز طولانی است" in message.status.replies[0]
