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

if not BOT_TOKEN:
    raise Exception(
        "BOT_TOKEN peyda nashod "
    )


ADMIN_IDS = [item.strip() for item in os.getenv("ADMIN_IDS", "106056586,69078288").split(",") if item.strip()]
ADMIN_REPORT_TIME = os.getenv("ADMIN_REPORT_TIME", "20:00")
