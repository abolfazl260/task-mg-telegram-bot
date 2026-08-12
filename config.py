import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from bot_platform import load_bot_profiles

# Keep Telegram transport noise out of the bot terminal while preserving
# application warnings/errors.
for _logger_name in ("httpx", "httpcore", "telegram.request", "telegram.ext._application"):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

# Install the media router before main.py creates its Application instances.
# This also works when main.py is executed as __main__.
try:
    import services.comment_media_router  # noqa: F401
except Exception:
    logging.getLogger(__name__).exception("Failed to install comment media router")

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env"
)


BOT_PROFILES = load_bot_profiles()
DEFAULT_BOT_PROFILE = BOT_PROFILES[0]
BOT_TOKEN = DEFAULT_BOT_PROFILE.token

# Used in deep-link invites (t.me/USERNAME?start=...)
BOT_USERNAME = DEFAULT_BOT_PROFILE.username

# Optional Groq integration for the /ai task assistant. Never hard-code API keys.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/responses")

ADMIN_IDS = [item.strip() for item in os.getenv("ADMIN_IDS", "106056586,69078288").split(",") if item.strip()]
ADMIN_REPORT_TIME = os.getenv("ADMIN_REPORT_TIME", "20:00")

# Telegram Business/Secretary mode. Enable Secretary Mode in @BotFather first.
SECRETARY_AUTO_REPLY_ENABLED = os.getenv("SECRETARY_AUTO_REPLY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
SECRETARY_AUTO_REPLY_TEXT = os.getenv(
    "SECRETARY_AUTO_REPLY_TEXT",
    "پیام شما دریافت شد؛ به‌زودی پاسخ می‌دهیم.",
)
