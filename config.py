import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env"
)


BOT_TOKEN = os.getenv("BOT_TOKEN")


if not BOT_TOKEN:
    raise Exception(
        "BOT_TOKEN peyda nashod "
    )