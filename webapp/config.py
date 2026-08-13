"""Environment-backed configuration for the Telegram Web App foundation."""
from __future__ import annotations

import os


WEBAPP_HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8081"))
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", "").strip()
# Keep the Web App tied to an explicitly selected bot. Do not silently use a
# different bot token when the project runs multiple bot profiles.
WEBAPP_BOT_TOKEN = os.getenv("WEBAPP_BOT_TOKEN", "").strip()
