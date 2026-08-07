"""Multi-bot profile loading and Telegram application orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application

BASE_DIR = Path(__file__).resolve().parent
BOTS_DIR = BASE_DIR / "bots"

DEFAULT_FEATURES = {
    "tasks": True,
    "teams": True,
    "templates": True,
    "habits": True,
    "reports": True,
    "donate": True,
    "ai": True,
    "guest_mode": True,
    "search": True,
    "bulk_import": True,
    "unassigned": True,
}

DEFAULT_MENU = [
    {"label": "➕ افزودن تسک", "callback_data": "add_task", "feature": "tasks"},
    {"label": "📋 تسک‌ها", "callback_data": "tasks", "feature": "tasks"},
    {"label": "👥 تیم‌ها", "callback_data": "teams", "feature": "teams"},
    {"label": "🧩 تمپلیت‌ها", "callback_data": "templates", "feature": "templates"},
    {"label": "🌱 مدیریت عادت‌ها", "callback_data": "habit_menu", "feature": "habits"},
    {"label": "📊 گزارشات", "callback_data": "stats", "feature": "reports"},
    {"label": "📖 راهنما", "callback_data": "help"},
    {"label": "⚙️ تنظیمات", "callback_data": "settings"},
    {"label": "📞 ارتباط با ما", "callback_data": "contact_us"},
]

DEFAULT_WORKFLOW = {
    "statuses": {
        "pending": "⏳ در انتظار",
        "in_progress": "🚀 در حال انجام",
        "done": "✅ انجام شده",
        "cancelled": "❌ لغو شده",
    },
    "actions": {
        "start": "🚀 شروع",
        "done": "✅ انجام شد",
        "cancel": "❌ لغو",
        "pending": "⏸ بازگشت به انتظار",
        "owner": "👤 مسئول",
        "take": "🙋 برعهده گرفتن",
    },
}


@dataclass(frozen=True)
class BotProfile:
    """Runtime configuration for one Telegram bot instance."""

    key: str
    name: str
    username: str
    token: str
    active: bool = True
    description: str = ""
    features: dict[str, bool] = field(default_factory=lambda: DEFAULT_FEATURES.copy())
    settings: dict[str, Any] = field(default_factory=dict)
    access: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_WORKFLOW)))
    menu: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_MENU))

    def feature_enabled(self, name: str) -> bool:
        return bool(self.features.get(name, False))


def _env_name(profile_key: str, field_name: str) -> str:
    safe_key = "".join(ch if ch.isalnum() else "_" for ch in profile_key).upper()
    return f"BOT_{safe_key}_{field_name.upper()}"


def _load_json_profile(path: Path) -> BotProfile:
    raw = json.loads(path.read_text(encoding="utf-8"))
    key = raw.get("key") or path.stem
    token_env = raw.get("token_env") or _env_name(key, "TOKEN")
    username_env = raw.get("username_env") or _env_name(key, "USERNAME")
    token = os.getenv(token_env, "").strip()
    if not token:
        raise RuntimeError(f"Token env var {token_env} is required for bot profile {key}.")
    username = os.getenv(username_env, raw.get("username", "")).strip().lstrip("@")
    if not username:
        raise RuntimeError(f"Username env var {username_env} or username field is required for bot profile {key}.")

    features = DEFAULT_FEATURES.copy()
    features.update(raw.get("features", {}))
    workflow = json.loads(json.dumps(DEFAULT_WORKFLOW))
    for section, values in raw.get("workflow", {}).items():
        if isinstance(values, dict) and isinstance(workflow.get(section), dict):
            workflow[section].update(values)
        else:
            workflow[section] = values

    return BotProfile(
        key=key,
        name=raw.get("name") or username,
        username=username,
        token=token,
        active=bool(raw.get("active", True)),
        description=raw.get("description", ""),
        features=features,
        settings=raw.get("settings", {}),
        access=raw.get("access", {}),
        workflow=workflow,
        menu=raw.get("menu", DEFAULT_MENU),
    )


def load_bot_profiles() -> list[BotProfile]:
    """Load one or many bot profiles from .env and bots/*.json files."""
    load_dotenv(BASE_DIR / ".env")
    profile_names = [item.strip() for item in os.getenv("BOT_PROFILES", "").split(",") if item.strip()]
    if profile_names:
        profiles = [_load_json_profile(BOTS_DIR / f"{name}.json") for name in profile_names]
    else:
        legacy_token = os.getenv("BOT_TOKEN", "").strip()
        if not legacy_token:
            raise RuntimeError("Set BOT_TOKEN for one bot or BOT_PROFILES with per-bot token env vars.")
        profile = BotProfile(
            key="default",
            name=os.getenv("BOT_NAME", "Task Manager Bot"),
            username=os.getenv("BOT_USERNAME", "TaskManagerpersian_Bot").lstrip("@"),
            token=legacy_token,
            description=os.getenv("BOT_DESCRIPTION", ""),
        )
        profiles = [profile]
    return [profile for profile in profiles if profile.active]


async def run_applications(apps: list[Application]) -> None:
    """Run multiple python-telegram-bot applications in one event loop."""
    for app in apps:
        await app.initialize()
        await app.start()
        if app.updater:
            await app.updater.start_polling(allowed_updates=[*Update.ALL_TYPES, "guest_message"])
    try:
        await asyncio.Event().wait()
    finally:
        for app in reversed(apps):
            if app.updater:
                await app.updater.stop()
            await app.stop()
            await app.shutdown()


def bot_logger(profile: BotProfile) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logging.getLogger(__name__), {"bot": profile.key})
