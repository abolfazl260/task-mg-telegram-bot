"""Generic Work Item Type / Vertical Entity Profile support.

Core knows only generic type metadata. Vertical-specific names and behavior are
provided by Bot Profile settings under settings.work_item_types.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bot_context import get_current_bot_key
from services.database import fetch_one

BASE_DIR = Path(__file__).resolve().parent.parent
BOTS_DIR = BASE_DIR / "bots"
TYPE_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

_DEFAULT_TYPE_DEFINITION = {
    "key": "task",
    "label_singular": "Task",
    "label_plural": "Tasks",
    "icon": "📝",
    "allowed_parent_types": [],
    "allowed_child_types": [],
    "status_profile": "default",
    "default_field_schema": {},
    "default_views": ["list", "detail"],
    "default_actions": ["create", "update", "status"],
    "feature_flags": ["tasks"],
}
_DEFAULT_PROFILE = {
    "default_type": "task",
    "types": [_DEFAULT_TYPE_DEFINITION],
}


def _clone(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def _string_list(value, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"invalid_work_item_type_profile:{field_name}")
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_definition(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("invalid_work_item_type_profile:type_definition")
    key = str(raw.get("key") or "").strip().lower()
    if not TYPE_KEY_RE.match(key):
        raise ValueError("invalid_work_item_type_profile:type_key")

    singular = str(raw.get("label_singular") or raw.get("label") or key).strip()
    plural = str(raw.get("label_plural") or singular).strip()
    if not singular or not plural:
        raise ValueError("invalid_work_item_type_profile:label")

    return {
        "key": key,
        "label_singular": singular,
        "label_plural": plural,
        "icon": str(raw.get("icon") or "").strip(),
        "allowed_parent_types": _string_list(raw.get("allowed_parent_types"), "allowed_parent_types"),
        "allowed_child_types": _string_list(raw.get("allowed_child_types"), "allowed_child_types"),
        "status_profile": _clone(raw.get("status_profile", "default")),
        "default_field_schema": _clone(raw.get("default_field_schema", {})),
        "default_views": _string_list(raw.get("default_views"), "default_views"),
        "default_actions": _string_list(raw.get("default_actions"), "default_actions"),
        "feature_flags": _string_list(raw.get("feature_flags"), "feature_flags"),
    }


def normalize_work_item_type_profile(settings: dict | None) -> dict[str, Any]:
    """Normalize and validate a profile's generic Work Item Type metadata."""
    settings = settings if isinstance(settings, dict) else {}
    raw_profile = settings.get("work_item_types")
    if raw_profile in (None, {}):
        raw_profile = _DEFAULT_PROFILE
    if not isinstance(raw_profile, dict):
        raise ValueError("invalid_work_item_type_profile")

    raw_types = raw_profile.get("types")
    if isinstance(raw_types, dict):
        raw_types = [
            {"key": key, **(value if isinstance(value, dict) else {})}
            for key, value in raw_types.items()
        ]
    if not isinstance(raw_types, list) or not raw_types:
        raise ValueError("invalid_work_item_type_profile:types")

    types: dict[str, dict[str, Any]] = {}
    for raw in raw_types:
        definition = _normalize_definition(raw)
        key = definition["key"]
        if key in types:
            raise ValueError("invalid_work_item_type_profile:duplicate_type")
        types[key] = definition

    default_type = str(raw_profile.get("default_type") or "").strip().lower()
    if not default_type:
        default_type = next(iter(types))
    if default_type not in types:
        raise ValueError("invalid_work_item_type_profile:default_type")

    known = set(types)
    for definition in types.values():
        for relation_field in ("allowed_parent_types", "allowed_child_types"):
            unknown = [key for key in definition[relation_field] if key not in known]
            if unknown:
                raise ValueError(f"invalid_work_item_type_profile:{relation_field}")

    return {"default_type": default_type, "types": types}


def validate_work_item_type_settings(settings: dict | None) -> dict[str, Any]:
    """Validate profile settings and return the normalized Work Item Type profile."""
    return normalize_work_item_type_profile(settings)


def _read_profile_file_settings(profile_key: str) -> dict:
    if not profile_key or not TYPE_KEY_RE.match(profile_key):
        return {}
    path = BOTS_DIR / f"{profile_key}.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    settings = payload.get("settings")
    return settings if isinstance(settings, dict) else {}


async def _profile_settings_async(bot_key: str) -> dict:
    row = await fetch_one("custom_bots", "bot_key=?", (bot_key,))
    if row:
        raw = row.get("settings_json")
        if raw:
            try:
                parsed = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            if isinstance(parsed, dict) and parsed.get("work_item_types"):
                return parsed

        base_profile = str(row.get("base_profile") or "").strip().lower()
        base_settings = _read_profile_file_settings(base_profile)
        if base_settings.get("work_item_types"):
            return base_settings

    file_settings = _read_profile_file_settings(bot_key)
    if file_settings.get("work_item_types"):
        return file_settings
    return {}


async def get_work_item_type_profile_async(bot_key: str | None = None) -> dict[str, Any]:
    key = str(bot_key or get_current_bot_key() or "default").strip().lower()
    settings = await _profile_settings_async(key)
    return normalize_work_item_type_profile(settings)


async def validate_work_item_type_async(
    work_item_type: str | None,
    bot_key: str | None = None,
) -> str:
    profile = await get_work_item_type_profile_async(bot_key)
    candidate = str(work_item_type or profile["default_type"]).strip().lower()
    if candidate not in profile["types"]:
        raise ValueError("invalid_work_item_type")
    return candidate


async def list_work_item_types_async(bot_key: str | None = None) -> list[dict[str, Any]]:
    profile = await get_work_item_type_profile_async(bot_key)
    default_type = profile["default_type"]
    return [
        {**_clone(definition), "is_default": key == default_type}
        for key, definition in profile["types"].items()
    ]
