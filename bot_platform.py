"""Multi-bot profile loading and Telegram application orchestration."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application

from services.bot_feature_registry import FEATURE_REGISTRY
from services.bot_management_service import seed_default_profiles
from services.bot_permission_registry import (
    normalize_permission_policy,
    permission_enabled as profile_permission_enabled,
)
from services.custom_bot_service import read_custom_bots
from services.database import _run
from services.task_capabilities import install_task_capabilities

BASE_DIR = Path(__file__).resolve().parent
BOTS_DIR = BASE_DIR / "bots"
DEFAULT_FEATURES = {name: True for name in FEATURE_REGISTRY}
COMMAND_TO_FEATURE = {"add": "tasks", "tasks": "tasks", "unassigned": "unassigned", "team": "teams", "search": "search", "templates": "templates", "reports": "reports", "habit": "habits", "donate": "donate", "ai": "ai", "jira": "integrations", "jira_status": "integrations", "jira_disconnect": "integrations"}
DEFAULT_MENU = [{"label": "➕ افزودن تسک", "callback_data": "add_task", "feature": "tasks"}, {"label": "📋 تسک‌ها", "callback_data": "tasks", "feature": "tasks"}, {"label": "🌱 عادت من", "callback_data": "habit_menu", "feature": "habits"}, {"label": "📊 گزارش", "callback_data": "stats", "feature": "reports"}, {"label": "📖 راهنما", "callback_data": "help"}, {"label": "⚙️ تنظیمات", "callback_data": "settings"}, {"label": "📞 ارتباط با ما", "callback_data": "contact_us", "feature": None}]
DEFAULT_WORKFLOW = {"statuses": {"pending": "⏳ در انتظار", "in_progress": "🚀 در حال انجام", "done": "✅ انجام شده", "cancelled": "❌ لغو شده"}, "actions": {"start": "🚀 شروع", "done": "✅ انجام شد", "cancel": "❌ لغو", "pending": "⏸ بازگشت به انتظار", "owner": "👤 مسئول", "take": "🙋 برعهده گرفتن"}}

@dataclass(frozen=True)
class BotProfile:
    key: str
    name: str
    username: str
    token: str
    active: bool = True
    description: str = ""
    features: dict[str, bool] = field(default_factory=lambda: DEFAULT_FEATURES.copy())
    permissions: dict[str, bool] = field(default_factory=dict)
    commands: tuple[str, ...] | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    access: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_WORKFLOW)))
    menu: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_MENU))
    def command_enabled(self, command: str) -> bool:
        if command in {"start", "help"}: return True
        if self.commands is None:
            feature = COMMAND_TO_FEATURE.get(command)
            return feature is None or self.feature_enabled(feature)
        return command in self.commands and (COMMAND_TO_FEATURE.get(command) is None or self.feature_enabled(COMMAND_TO_FEATURE[command]))
    def feature_enabled(self, name: str) -> bool:
        if not bool(self.features.get(name, False)): return False
        if self.commands is not None:
            commands_for_feature = [c for c, feature in COMMAND_TO_FEATURE.items() if feature == name]
            if commands_for_feature and not any(c in self.commands for c in commands_for_feature): return False
        return True
    def permission_enabled(self, permission_key: str) -> bool:
        enabled_features = [name for name, enabled in self.features.items() if enabled]
        return profile_permission_enabled(
            self.permissions,
            permission_key,
            enabled_features,
        )

def _env_name(profile_key: str, field_name: str) -> str:
    safe_key = "".join(ch if ch.isalnum() else "_" for ch in profile_key).upper()
    return f"BOT_{safe_key}_{field_name.upper()}"

def _load_json_profile(path: Path) -> BotProfile:
    raw = json.loads(path.read_text(encoding="utf-8")); key = raw.get("key") or path.stem
    token_env = raw.get("token_env") or _env_name(key, "TOKEN"); username_env = raw.get("username_env") or _env_name(key, "USERNAME")
    token = os.getenv(token_env, "").strip()
    if not token: raise RuntimeError(f"Token env var {token_env} is required for bot profile {key}.")
    username = os.getenv(username_env, raw.get("username", "")).strip().lstrip("@")
    if not username: raise RuntimeError(f"Username env var {username_env} or username field is required for bot profile {key}.")
    features = DEFAULT_FEATURES.copy(); features.update(raw.get("features", {}))
    # Backward-compatible migration for legacy JSON profiles: derive newly
    # granular Core features from the existing task_options contract.
    task_options = {}
    if isinstance(raw.get("settings"), dict) and isinstance(raw["settings"].get("task_options"), dict):
        task_options.update(raw["settings"]["task_options"])
    if isinstance(raw.get("task_options"), dict):
        task_options.update(raw["task_options"])
    option_features = {
        "allow_assignment": "assignment",
        "allow_tags": "tags",
        "allow_comments": "comments",
        "allow_categories": "categories",
        "allow_search": "search",
        "allow_templates": "templates",
        "allow_bulk_import": "bulk_import",
    }
    for option, feature in option_features.items():
        if option in task_options:
            features[feature] = bool(task_options[option])
    if not features.get("tasks", False):
        for feature in ("assignment","comments","attachments","tags","categories","priority","deadline","reminders","unassigned"):
            features[feature] = False
    if not features.get("ai", False):
        features["voice"] = False
    raw_commands = raw.get("commands")
    commands = tuple(dict.fromkeys(str(c).strip().lstrip("/") for c in raw_commands if str(c).strip())) if isinstance(raw_commands, list) else None
    workflow = json.loads(json.dumps(DEFAULT_WORKFLOW))
    for section, values in raw.get("workflow", {}).items():
        if isinstance(values, dict) and isinstance(workflow.get(section), dict): workflow[section].update(values)
        else: workflow[section] = values
    enabled_features = [name for name, enabled in features.items() if enabled]
    permissions = normalize_permission_policy(raw.get("permissions"), enabled_features)
    return BotProfile(key=key, name=raw.get("name") or username, username=username, token=token, active=bool(raw.get("active", True)), description=raw.get("description", ""), features=features, permissions=permissions, commands=commands, settings=raw.get("settings", {}), access=raw.get("access", {}), workflow=workflow, menu=raw.get("menu", DEFAULT_MENU))

def _legacy_default_profile() -> BotProfile | None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token: return None
    return BotProfile(key="default", name=os.getenv("BOT_NAME", "Task Manager Bot"), username=os.getenv("BOT_USERNAME", "TaskManagerpersian_Bot").lstrip("@"), token=token, description=os.getenv("BOT_DESCRIPTION", ""))

def _json_field(row: dict, name: str, default):
    raw = row.get(name)
    if raw in (None, ""):
        return default
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default
    return value


def _custom_bot_profiles() -> list[BotProfile]:
    profiles = []
    for row in read_custom_bots(include_tokens=True):
        if row.get("status") != "active" or not row.get("bot_token"):
            continue
        features = {name: False for name in DEFAULT_FEATURES}
        selected = [item.strip() for item in str(row.get("features") or "").split(",") if item.strip()]
        for feature in selected:
            if feature in DEFAULT_FEATURES:
                features[feature] = True
        if "custom_bots" not in selected:
            features["custom_bots"] = False
        commands_json = _json_field(row, "commands_json", None)
        if isinstance(commands_json, list) and commands_json:
            commands = tuple(dict.fromkeys(str(c).strip().lstrip("/") for c in commands_json if str(c).strip()))
        else:
            commands = tuple(c for c, feature in COMMAND_TO_FEATURE.items() if feature in selected)
        workflow = json.loads(json.dumps(DEFAULT_WORKFLOW))
        workflow_override = _json_field(row, "workflow_json", {})
        if isinstance(workflow_override, dict):
            for section, values in workflow_override.items():
                if isinstance(values, dict) and isinstance(workflow.get(section), dict):
                    workflow[section].update(values)
                else:
                    workflow[section] = values
        menu = _json_field(row, "menu_json", DEFAULT_MENU)
        if not isinstance(menu, list) or not menu:
            menu = list(DEFAULT_MENU)
        settings = _json_field(row, "settings_json", {})
        permissions = normalize_permission_policy(
            _json_field(row, "permissions_json", {}),
            selected,
        )
        profiles.append(
            BotProfile(
                key=row.get("bot_key") or f"custom_{row.get('owner_user_id', 'user')}",
                name=row.get("display_name") or row.get("owner_name") or row.get("bot_key") or "TaskMG Bot",
                username=(row.get("bot_username") or row.get("bot_key") or "custom_bot").lstrip("@"),
                token=row.get("bot_token", ""),
                description=row.get("description") or "Managed TaskMG Bot Profile.",
                features=features,
                permissions=permissions,
                commands=commands,
                settings=settings if isinstance(settings, dict) else {},
                access={"managed": True, "profile_type": row.get("profile_type") or "custom"},
                workflow=workflow,
                menu=menu,
            )
        )
    return profiles

def load_bot_profiles() -> list[BotProfile]:
    load_dotenv(BASE_DIR / ".env")
    if os.getenv("TESTING", "").lower() in {"1", "true", "yes", "on"}: return [BotProfile(key="test", name="Test Bot", username="test_bot", token="test-token")]
    # JSON profiles are migration/compatibility inputs. Once a bot_key exists in
    # the managed store, that row is authoritative even when it is inactive.
    _run(seed_default_profiles())
    managed_rows = read_custom_bots(include_tokens=True)
    managed_keys = {str(row.get("bot_key") or "").strip() for row in managed_rows if row.get("bot_key")}
    profile_names = [item.strip() for item in os.getenv("BOT_PROFILES", "").split(",") if item.strip()]; profiles: list[BotProfile] = []; legacy_profile = _legacy_default_profile()
    if legacy_profile is not None: profiles.append(legacy_profile)
    file_profile_names = [name for name in profile_names if name not in managed_keys]
    if file_profile_names: profiles.extend(_load_json_profile(BOTS_DIR / f"{name}.json") for name in file_profile_names)
    elif profile_names and not managed_keys and not profiles: raise RuntimeError("Set BOT_TOKEN for one bot or BOT_PROFILES with per-bot token env vars.")
    elif not profile_names and not profiles and not managed_rows:
        raise RuntimeError("Set BOT_TOKEN, BOT_PROFILES, or configure a managed Bot Profile.")
    profiles.extend(_custom_bot_profiles()); unique: dict[str, BotProfile] = {}
    for profile in profiles:
        if profile.active: unique[profile.key] = profile
    return list(unique.values())

async def _cleanup_application_resources(app: Application) -> None:
    runner = app.bot_data.pop("integration_oauth_runner", None)
    if runner is not None:
        try: await runner.cleanup()
        except Exception: logging.getLogger(__name__).exception("Failed to cleanup OAuth runner")

async def run_applications(apps: list[Application], post_init_hook: Callable[[Application], Awaitable[None]] | None = None) -> None:
    started: list[Application] = []
    resource_stop = asyncio.Event()
    from services.resource_monitor import monitor_resources
    resource_monitor_task = asyncio.create_task(monitor_resources(resource_stop), name="resource-monitor")
    try:
        for app in apps:
            install_task_capabilities(app); await app.initialize()
            callback = post_init_hook if post_init_hook is not None else getattr(app, "post_init", None)
            if callback is not None: await callback(app)
            await app.start()
            if app.updater: await app.updater.start_polling(allowed_updates=[*Update.ALL_TYPES, "guest_message"])
            started.append(app)
        await asyncio.Event().wait()
    finally:
        resource_stop.set(); resource_monitor_task.cancel()
        try: await resource_monitor_task
        except asyncio.CancelledError: pass
        for app in reversed(started):
            try:
                if app.updater and app.updater.running: await app.updater.stop()
            finally:
                try:
                    await _cleanup_application_resources(app)
                finally:
                    try: await app.stop()
                    finally: await app.shutdown()
        try:
            from webapp.runtime import stop_webapp_server
            stop_webapp_server()
        except Exception: logging.getLogger(__name__).exception("Failed to stop webapp server during shutdown")
        try:
            from services.database import close_all_dbs
            await close_all_dbs()
        except Exception: logging.getLogger(__name__).exception("Failed to close database connections during shutdown")
        try:
            from services.database import shutdown_sync_loop
            shutdown_sync_loop()
        except Exception: logging.getLogger(__name__).exception("Failed to close database compatibility loop during shutdown")

def bot_logger(profile: BotProfile) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logging.getLogger(__name__), {"bot": profile.key})
