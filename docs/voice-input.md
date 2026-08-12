# Telegram Voice Input

TaskBot can accept a Telegram Voice Message and send its recognized text through the same AI pipeline used by `/ai` text input.

## How to use

1. Open the bot in Telegram.
2. Record and send a **Voice Message** (the microphone/voice-note format, not a regular audio file).
3. The bot downloads the Telegram voice file and shows `🎤 در حال پردازش وویس...`.
4. The configured Speech-to-Text provider transcribes the audio.
5. The resulting text is passed to the existing AI command pipeline, so task/habit creation and AI answers use the same logic as text input.

Example voice content:

> فردا ساعت ۹ جلسه با تیم فروش دارم

The transcription is processed as if the user had entered the same text through the existing AI input flow.

## Environment variables

```env
STT_PROVIDER=groq
STT_API_KEY=
STT_API_URL=https://api.groq.com/openai/v1/audio/transcriptions
STT_MODEL=whisper-large-v3-turbo
STT_LANGUAGE=
VOICE_MAX_SIZE_MB=20
VOICE_MAX_DURATION_SECONDS=300
```

`STT_API_KEY` may be omitted when `GROQ_API_KEY` is already configured. `STT_LANGUAGE` is optional; leaving it empty allows the provider to auto-detect the language. No language is hard-coded in the voice handler.

## Architecture

```text
Telegram Voice
    ↓
handlers/voice.py
    ↓
SpeechToTextService
    ↓
GroqSpeechToTextService (current provider)
    ↓
transcribed text
    ↓
existing handlers.ai.ai_command
    ↓
existing AI / Task / Habit logic
```

The `SpeechToTextService` abstraction keeps provider-specific code separate from Telegram and business logic. A future provider or language can therefore be introduced without changing task/habit processing.

## Limits and errors

The handler rejects voice messages that exceed `VOICE_MAX_SIZE_MB` or `VOICE_MAX_DURATION_SECONDS`. Download failures, invalid/empty audio, provider failures, unavailable configuration, and empty transcriptions are converted into user-friendly Telegram messages; raw exceptions and stack traces are not shown to users.
