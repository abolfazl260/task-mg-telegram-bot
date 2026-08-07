import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env"
)


BOT_TOKEN = os.getenv("BOT_TOKEN")

# Used in deep-link invites (t.me/USERNAME?start=...)
BOT_USERNAME = os.getenv("BOT_USERNAME", "TaskManagerpersian_Bot").lstrip("@")

# Optional Groq integration for the /ai task assistant. Never hard-code API keys.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/responses")

if not BOT_TOKEN:
    raise Exception(
        "BOT_TOKEN peyda nashod "
    )


ADMIN_IDS = [item.strip() for item in os.getenv("ADMIN_IDS", "106056586,69078288").split(",") if item.strip()]
ADMIN_REPORT_TIME = os.getenv("ADMIN_REPORT_TIME", "20:00")
