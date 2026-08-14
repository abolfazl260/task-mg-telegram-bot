"""Environment-backed configuration for the Telegram Web App foundation."""
from __future__ import annotations

import os

WEBAPP_HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8081"))
WEBAPP_PUBLIC_HOST = os.getenv("WEBAPP_PUBLIC_HOST", "127.0.0.1").strip()
WEBAPP_SCHEME = os.getenv("WEBAPP_SCHEME", "http").strip() or "http"
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", f"{WEBAPP_SCHEME}://{WEBAPP_PUBLIC_HOST}:{WEBAPP_PORT}").strip().rstrip("/")
