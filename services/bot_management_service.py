"""Managed Bot Profile service used by Admin Back Office and runtime.

The existing custom_bots table remains the authoritative persistence model.
This module evolves that table in-place and keeps legacy callers compatible.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import aiohttp

from services.bot_feature_registry import (
    DEFAULT_PROFILE_TEMPLATES,
    normalize_features,
    registry_payload,
)
from services.database import get_db

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")
BOT_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
STATUS_VALUES = {"active", "inactive"}

_REQUIRED_COLUMNS = {
    "display_name": "TEXT NOT NULL DEFAULT ''",
    "description": "TEXT NOT NULL DEFAULT ''",
    "profile_type": "TEXT NOT NULL DEFAULT 'custom'",
    "base_profile": "TEXT NOT NULL DEFAULT ''",
    "settings_json": "TEXT NOT NULL DEFAULT '{}'",
    "permissions_json": "TEXT NOT NULL DEFAULT '{}'",
    "commands_json": "TEXT NOT NULL DEFAULT '[]'",
    "workflow_json": "TEXT NOT NULL DEFAULT '{}'",
    "menu_json": "TEXT NOT NULL DEFAULT '[]'",
    "source": "TEXT NOT NULL DEFAULT 'managed'",
    "last_error": "TEXT NOT NULL DEFAULT ''",
    "last_connectivity_check": "TEXT NOT NULL DEFAULT ''",
}

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_management_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_key TEXT NOT NULL,
    actor_user_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bot_management_audit_bot
ON bot_management_audit(bot_key, created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value, fallback):
    if value is None:
        return json.dumps(fallback, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError:
            raise ValueError("invalid_json")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def mask_token(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    if ":" not in token:
        return "••••••••"
    prefix, secret = token.split(":", 1)
    tail = secret[-4:] if len(secret) >= 4 else ""
    return f"{prefix}:••••••••••••{tail}"


async def ensure_bot_management_schema() -> None:
    db = await get_db()
    async with db.lock:
        await db.conn.executescript(_AUDIT_SCHEMA)
        async with db.conn.execute("PRAGMA table_info(custom_bots)") as cur:
            existing = {row[1] for row in await cur.fetchall()}
        for name, definition in _REQUIRED_COLUMNS.items():
            if name not in existing:
                await db.conn.execute(f"ALTER TABLE custom_bots ADD COLUMN {name} {definition}")
        await db.conn.commit()


async def _audit(bot_key: str, actor_user_id: object, action: str, details: dict | None = None) -> None:
    db = await get_db()
    safe_details = dict(details or {})
    safe_details.pop("bot_token", None)
    safe_details.pop("token", None)
    await db.conn.execute(
        "INSERT INTO bot_management_audit(bot_key,actor_user_id,action,details_json,created_at) VALUES(?,?,?,?,?)",
        (bot_key, str(actor_user_id or ""), action, _json(safe_details, {}), _now()),
    )
    await db.conn.commit()


async def validate_telegram_token(token: str) -> dict:
    token = (token or "").strip()
    if not TOKEN_RE.match(token):
        raise ValueError("invalid_token")
    timeout = aiohttp.ClientTimeout(total=8)
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                payload = await response.json(content_type=None)
                response_ok = response.status == 200
    except Exception as exc:
        raise ValueError("telegram_validation_unavailable") from exc
    if not response_ok or not isinstance(payload, dict) or not payload.get("ok"):
        raise ValueError("invalid_token")
    result = payload.get("result") or {}
    if not result.get("id") or not result.get("username"):
        raise ValueError("invalid_token")
    return {"id": result["id"], "username": str(result["username"]).lstrip("@")}


def _public_row(row: dict) -> dict:
    data = dict(row)
    token = str(data.pop("bot_token", "") or "")
    data["token_configured"] = bool(token)
    data["token_masked"] = mask_token(token)
    features = [item for item in str(data.get("features") or "").split(",") if item]
    data["features"] = features
    data["enabled_feature_count"] = len(features)
    for field in ("settings_json", "permissions_json", "commands_json", "workflow_json", "menu_json"):
        raw = data.pop(field, "")
        default = [] if field in {"commands_json", "menu_json"} else {}
        try:
            data[field.removesuffix("_json")] = json.loads(raw or json.dumps(default))
        except json.JSONDecodeError:
            data[field.removesuffix("_json")] = default
    return data


async def list_managed_bots(*, include_tokens: bool = False) -> list[dict]:
    await ensure_bot_management_schema()
    db = await get_db()
    async with db.conn.execute("SELECT * FROM custom_bots ORDER BY created_at, bot_key") as cur:
        rows = [dict(row) for row in await cur.fetchall()]
    return rows if include_tokens else [_public_row(row) for row in rows]


async def get_managed_bot(bot_key: str, *, include_token: bool = False) -> dict | None:
    await ensure_bot_management_schema()
    db = await get_db()
    async with db.conn.execute("SELECT * FROM custom_bots WHERE bot_key=?", (bot_key,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    data = dict(row)
    return data if include_token else _public_row(data)


async def create_managed_bot(
    payload: dict,
    actor_user_id: object,
    *,
    token_validator: Callable[[str], Awaitable[dict]] = validate_telegram_token,
) -> dict:
    await ensure_bot_management_schema()
    bot_key = str(payload.get("bot_key") or "").strip().lower()
    if not BOT_KEY_RE.match(bot_key):
        raise ValueError("invalid_bot_key")
    if await get_managed_bot(bot_key, include_token=True):
        raise ValueError("duplicate_bot_key")
    status = str(payload.get("status") or "inactive").strip().lower()
    if status not in STATUS_VALUES:
        raise ValueError("invalid_status")
    token = str(payload.get("bot_token") or "").strip()
    token_info = None
    if token:
        token_info = await token_validator(token)
    if status == "active" and not token:
        raise ValueError("active_bot_requires_token")
    features = normalize_features(payload.get("features"))
    username = str(payload.get("bot_username") or "").strip().lstrip("@")
    if token_info and not username:
        username = token_info["username"]
    now = _now()
    db = await get_db()
    async with db.lock:
        await db.conn.execute(
            """INSERT INTO custom_bots(
                bot_key,owner_user_id,owner_name,owner_username,bot_token,bot_username,
                features,status,pricing_plan,created_at,updated_at,display_name,description,
                profile_type,base_profile,settings_json,permissions_json,commands_json,
                workflow_json,menu_json,source,last_error,last_connectivity_check
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                bot_key, None, "", "", token, username, ",".join(features), status,
                "managed", now, now,
                str(payload.get("display_name") or bot_key).strip(),
                str(payload.get("description") or "").strip(),
                str(payload.get("profile_type") or "custom").strip() or "custom",
                str(payload.get("base_profile") or "").strip(),
                _json(payload.get("settings"), {}),
                _json(payload.get("permissions"), {}),
                _json(payload.get("commands"), []),
                _json(payload.get("workflow"), {}),
                _json(payload.get("menu"), []),
                "managed", "", now if token_info else "",
            ),
        )
        await db.conn.commit()
    await _audit(bot_key, actor_user_id, "bot_created", {"status": status, "features": features})
    return await get_managed_bot(bot_key)


async def update_managed_bot(
    bot_key: str,
    payload: dict,
    actor_user_id: object,
    *,
    token_validator: Callable[[str], Awaitable[dict]] = validate_telegram_token,
) -> dict:
    await ensure_bot_management_schema()
    existing = await get_managed_bot(bot_key, include_token=True)
    if not existing:
        raise ValueError("bot_not_found")
    status = str(payload.get("status", existing.get("status") or "inactive")).strip().lower()
    if status not in STATUS_VALUES:
        raise ValueError("invalid_status")
    replacement = str(payload.get("bot_token") or "").strip()
    token = replacement or str(existing.get("bot_token") or "")
    token_info = None
    if replacement:
        token_info = await token_validator(replacement)
    if status == "active" and not token:
        raise ValueError("active_bot_requires_token")
    features = normalize_features(
        payload.get("features") if "features" in payload
        else str(existing.get("features") or "").split(",")
    )
    username = str(payload.get("bot_username", existing.get("bot_username") or "")).strip().lstrip("@")
    if token_info and not username:
        username = token_info["username"]
    db = await get_db()
    async with db.lock:
        await db.conn.execute(
            """UPDATE custom_bots SET
                bot_token=?,bot_username=?,features=?,status=?,updated_at=?,
                display_name=?,description=?,profile_type=?,base_profile=?,
                settings_json=?,permissions_json=?,commands_json=?,workflow_json=?,menu_json=?,
                last_error=?,last_connectivity_check=?
               WHERE bot_key=?""",
            (
                token, username, ",".join(features), status, _now(),
                str(payload.get("display_name", existing.get("display_name") or bot_key)).strip(),
                str(payload.get("description", existing.get("description") or "")).strip(),
                str(payload.get("profile_type", existing.get("profile_type") or "custom")).strip(),
                str(payload.get("base_profile", existing.get("base_profile") or "")).strip(),
                _json(payload.get("settings", existing.get("settings_json") or "{}"), {}),
                _json(payload.get("permissions", existing.get("permissions_json") or "{}"), {}),
                _json(payload.get("commands", existing.get("commands_json") or "[]"), []),
                _json(payload.get("workflow", existing.get("workflow_json") or "{}"), {}),
                _json(payload.get("menu", existing.get("menu_json") or "[]"), []),
                "", _now() if token_info else str(existing.get("last_connectivity_check") or ""),
                bot_key,
            ),
        )
        await db.conn.commit()
    action = "token_replaced" if replacement else "configuration_edited"
    await _audit(bot_key, actor_user_id, action, {"status": status, "features": features})
    return await get_managed_bot(bot_key)


async def set_bot_status(
    bot_key: str,
    active: bool,
    actor_user_id: object,
    *,
    token_validator: Callable[[str], Awaitable[dict]] = validate_telegram_token,
) -> dict:
    existing = await get_managed_bot(bot_key, include_token=True)
    if not existing:
        raise ValueError("bot_not_found")
    db = await get_db()
    if active:
        token = str(existing.get("bot_token") or "")
        if not token:
            raise ValueError("active_bot_requires_token")
        try:
            info = await token_validator(token)
        except ValueError as exc:
            await db.conn.execute(
                "UPDATE custom_bots SET last_error=?,updated_at=? WHERE bot_key=?",
                (str(exc), _now(), bot_key),
            )
            await db.conn.commit()
            raise
        await db.conn.execute(
            "UPDATE custom_bots SET status='active',bot_username=COALESCE(NULLIF(bot_username,''),?),last_error='',last_connectivity_check=?,updated_at=? WHERE bot_key=?",
            (info["username"], _now(), _now(), bot_key),
        )
        await db.conn.commit()
        await _audit(bot_key, actor_user_id, "bot_activated")
    else:
        await db.conn.execute(
            "UPDATE custom_bots SET status='inactive',updated_at=? WHERE bot_key=?",
            (_now(), bot_key),
        )
        await db.conn.commit()
        await _audit(bot_key, actor_user_id, "bot_deactivated")
    return await get_managed_bot(bot_key)


async def validate_token_only(token: str) -> dict:
    info = await validate_telegram_token(token)
    return {"valid": True, "username": info["username"]}


async def list_audit_events(bot_key: str, limit: int = 50) -> list[dict]:
    await ensure_bot_management_schema()
    db = await get_db()
    async with db.conn.execute(
        "SELECT bot_key,actor_user_id,action,details_json,created_at FROM bot_management_audit WHERE bot_key=? ORDER BY id DESC LIMIT ?",
        (bot_key, max(1, min(int(limit), 200))),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


async def seed_default_profiles() -> list[str]:
    """Seed Simple and Clinic templates without creating duplicate Clinic implementations."""
    await ensure_bot_management_schema()
    db = await get_db()
    seeded: list[str] = []
    clinic_path = BASE_DIR / "bots" / "clinic.json"
    clinic = {}
    if clinic_path.exists():
        try:
            clinic = json.loads(clinic_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("clinic_profile_seed_read_failed")

    for key, template in DEFAULT_PROFILE_TEMPLATES.items():
        if await get_managed_bot(key, include_token=True):
            continue
        now = _now()
        settings = clinic.get("settings", {}) if key == "clinic" else {}
        commands = clinic.get("commands", []) if key == "clinic" else ["start", "add", "tasks", "help"]
        workflow = clinic.get("workflow", {}) if key == "clinic" else {}
        menu = clinic.get("menu", []) if key == "clinic" else []
        username = clinic.get("username", "") if key == "clinic" else ""
        token = ""
        status = "inactive"
        source = "seed"
        if key == "clinic":
            configured_profiles = {item.strip() for item in os.getenv("BOT_PROFILES", "").split(",") if item.strip()}
            if "clinic" in configured_profiles:
                token_env = clinic.get("token_env") or "BOT_CLINIC_TOKEN"
                username_env = clinic.get("username_env") or "BOT_CLINIC_USERNAME"
                token = os.getenv(token_env, "").strip()
                username = os.getenv(username_env, username).strip().lstrip("@")
                if token:
                    status = "active"
                    source = "migrated_json"
        await db.conn.execute(
            """INSERT INTO custom_bots(
                bot_key,owner_user_id,owner_name,owner_username,bot_token,bot_username,
                features,status,pricing_plan,created_at,updated_at,display_name,description,
                profile_type,base_profile,settings_json,permissions_json,commands_json,
                workflow_json,menu_json,source,last_error,last_connectivity_check
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                key, None, "", "", token, username,
                ",".join(normalize_features(template["features"])), status, "template",
                now, now, template["name"], template["description"], key, key,
                _json(settings, {}), "{}", _json(commands, []), _json(workflow, {}),
                _json(menu, []), source, "", "",
            ),
        )
        await db.conn.commit()
        seeded.append(key)
    return seeded


def feature_registry_payload() -> list[dict]:
    return registry_payload()
