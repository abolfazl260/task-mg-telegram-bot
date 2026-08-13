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
from services.custom_bot_service import read_custom_bots
from services.task_capabilities import install_task_capabilities
from telegram.ext import Application

BASE_DIR = Path(__file__).resolve().parent
BOTS_DIR = BASE_DIR / "bots"

DEFAULT_FEATURES = {
    "custom_bots": True,
    "integrations": True,
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


def _legacy_default_profile() -> BotProfile | None:
    """Load the original BOT_TOKEN bot when present, even in multi-bot mode."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        return None
    return BotProfile(
        key="default",
        name=os.getenv("BOT_NAME", "Task Manager Bot"),
        username=os.getenv("BOT_USERNAME", "TaskManagerpersian_Bot").lstrip("@"),
        token=token,
        description=os.getenv("BOT_DESCRIPTION", ""),
    )


def _custom_bot_profiles() -> list[BotProfile]:
    profiles = []
    for row in read_custom_bots(include_tokens=True):
        if row.get("status") != "active" or not row.get("bot_token"):
            continue
        # A custom bot starts with every feature disabled. The selected
        # features from the management UI are then enabled explicitly.
        features = {name: False for name in DEFAULT_FEATURES}
        for feature in [item.strip() for item in row.get("features", "").split(",") if item.strip()]:
            if feature in DEFAULT_FEATURES:
                features[feature] = True
        features["custom_bots"] = False
        profiles.append(BotProfile(
            key=row.get("bot_key") or f"custom_{row.get('owner_user_id', 'user')}",
            name=f"ربات اختصاصی {row.get('owner_name') or row.get('owner_user_id')}",
            username=(row.get("bot_username") or row.get("bot_key") or "custom_bot").lstrip("@"),
            token=row.get("bot_token", ""),
            description="ربات اختصاصی ساخته‌شده توسط کاربر؛ فعلاً رایگان در نسخه بتا.",
            features=features,
            settings={"pricing_plan": row.get("pricing_plan", "free_beta"), "owner_user_id": row.get("owner_user_id", ""), "habit_only": "habits" in [x.strip() for x in row.get("features", "").split(",") if x.strip()] and "tasks" not in [x.strip() for x in row.get("features", "").split(",") if x.strip()]},
        ))
    return profiles


def load_bot_profiles() -> list[BotProfile]:
    """Load the legacy bot, static profiles, and active self-service custom bots."""
    load_dotenv(BASE_DIR / ".env")
    profile_names = [item.strip() for item in os.getenv("BOT_PROFILES", "").split(",") if item.strip()]

    # BOT_TOKEN remains the original Task Manager bot. It is intentionally
    # loaded alongside BOT_PROFILES so adding a second bot cannot disable it.
    profiles: list[BotProfile] = []
    legacy_profile = _legacy_default_profile()
    if legacy_profile is not None:
        profiles.append(legacy_profile)

    if profile_names:
        profiles.extend(_load_json_profile(BOTS_DIR / f"{name}.json") for name in profile_names)
    elif not profiles:
        raise RuntimeError("Set BOT_TOKEN for one bot or BOT_PROFILES with per-bot token env vars.")

    profiles.extend(_custom_bot_profiles())

    # Avoid starting the same profile twice if the legacy/default profile is
    # also listed explicitly in BOT_PROFILES.
    unique: dict[str, BotProfile] = {}
    for profile in profiles:
        if profile.active:
            unique[profile.key] = profile
    return list(unique.values())


async def run_applications(apps: list[Application]) -> None:
    """Run multiple python-telegram-bot applications in one event loop."""
    for app in apps:
        # Apply per-profile task options after all handlers are registered.
        # This keeps the core task handler shared by every bot while allowing
        # each profile to enable/disable assignment, tags, comments, etc.
        install_task_capabilities(app)
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
