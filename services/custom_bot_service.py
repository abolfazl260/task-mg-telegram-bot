"""Self-service custom Telegram bot provisioning requests."""

from __future__ import annotations

import csv
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

FILE_PATH = Path("data/custom_bots.csv")
HEADERS = [
    "bot_key",
    "owner_user_id",
    "owner_name",
    "owner_username",
    "bot_token",
    "bot_username",
    "features",
    "status",
    "pricing_plan",
    "created_at",
    "updated_at",
]

FEATURE_OPTIONS = {
    "tasks": "✅ مدیریت تسک",
    "teams": "👥 تیم و فضای مشترک",
    "templates": "🧩 تمپلیت‌ها",
    "habits": "🌱 مدیریت عادت‌ها",
    "reports": "📊 گزارشات",
    "search": "🔎 جستجو و اشتراک‌گذاری",
    "bulk_import": "📥 ورود گروهی",
    "ai": "🤖 دستیار هوشمند",
    "guest_mode": "👤 Guest Mode",
}

DEFAULT_SELECTED_FEATURES = ["tasks", "teams", "reports", "search"]
TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


def init_custom_bots() -> None:
    os.makedirs(FILE_PATH.parent, exist_ok=True)
    if not FILE_PATH.exists():
        with FILE_PATH.open("w", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, fieldnames=HEADERS).writeheader()
        return
    rows = read_custom_bots(include_tokens=True)
    _write_all(rows)


def read_custom_bots(include_tokens: bool = False) -> list[dict]:
    if not FILE_PATH.exists():
        return []
    with FILE_PATH.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for header in HEADERS:
            row.setdefault(header, "")
        if not include_tokens:
            row["bot_token"] = ""
    return rows


def _write_all(rows: list[dict]) -> None:
    os.makedirs(FILE_PATH.parent, exist_ok=True)
    with FILE_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in HEADERS})


def validate_bot_token(token: str) -> bool:
    return bool(TOKEN_RE.match((token or "").strip()))


def normalize_features(features: list[str] | None) -> list[str]:
    selected = [f for f in (features or DEFAULT_SELECTED_FEATURES) if f in FEATURE_OPTIONS]
    return selected or DEFAULT_SELECTED_FEATURES.copy()


def create_custom_bot_request(user, token: str, features: list[str], bot_username: str = "") -> dict:
    token = (token or "").strip()
    if not validate_bot_token(token):
        raise ValueError("invalid_token")

    rows = read_custom_bots(include_tokens=True)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    owner_id = str(user.id)
    existing = next((row for row in rows if row.get("owner_user_id") == owner_id and row.get("bot_token") == token), None)
    selected = normalize_features(features)
    if existing:
        existing.update({
            "owner_name": user.full_name or "",
            "owner_username": user.username or "",
            "bot_username": bot_username or existing.get("bot_username", ""),
            "features": ",".join(selected),
            "status": "active",
            "pricing_plan": "free_beta",
            "updated_at": now,
        })
        row = existing
    else:
        row = {
            "bot_key": f"custom_{owner_id}_{secrets.token_hex(3)}",
            "owner_user_id": owner_id,
            "owner_name": user.full_name or "",
            "owner_username": user.username or "",
            "bot_token": token,
            "bot_username": bot_username.strip().lstrip("@"),
            "features": ",".join(selected),
            "status": "active",
            "pricing_plan": "free_beta",
            "created_at": now,
            "updated_at": now,
        }
        rows.append(row)
    _write_all(rows)
    return {**row, "bot_token": ""}
