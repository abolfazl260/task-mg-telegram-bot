"""Environment-backed configuration for the Telegram Web App foundation."""
from __future__ import annotations

import os

from dotenv import load_dotenv

# This module is imported while handlers are being bootstrapped, before
# bot_platform loads the environment. Load the project .env here as well so
# report links never freeze the localhost defaults during early imports.
load_dotenv()

WEBAPP_HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8081"))
WEBAPP_PUBLIC_HOST = os.getenv("WEBAPP_PUBLIC_HOST", "127.0.0.1").strip()
WEBAPP_SCHEME = os.getenv("WEBAPP_SCHEME", "http").strip() or "http"
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", f"{WEBAPP_SCHEME}://{WEBAPP_PUBLIC_HOST}:{WEBAPP_PORT}").strip().rstrip("/")
