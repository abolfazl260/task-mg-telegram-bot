from __future__ import annotations
import secrets

from services.bot_feature_registry import FEATURE_REGISTRY, normalize_features as _normalize_features
from services.bot_management_service import TOKEN_RE
from services.database import sync_all, sync_one, sync_execute

FEATURE_OPTIONS = {
    key: definition.label
    for key, definition in FEATURE_REGISTRY.items()
    if key in {"tasks", "teams", "templates", "habits", "reports", "search", "bulk_import", "ai", "guest_mode"}
}
DEFAULT_SELECTED_FEATURES = ["core", "tasks", "teams", "reports", "search"]


def init_custom_bots():
    from services.database import _run, init_db
    from services.bot_management_service import seed_default_profiles
    _run(init_db())
    _run(seed_default_profiles())


def read_custom_bots(include_tokens=False):
    rows = sync_all("custom_bots")
    if not include_tokens:
        for row in rows:
            row["bot_token"] = ""
    return rows


def validate_bot_token(token):
    return bool(TOKEN_RE.match((token or "").strip()))


def normalize_features(features):
    selected = [x for x in (features or DEFAULT_SELECTED_FEATURES) if x in FEATURE_OPTIONS or x == "core"]
    if not selected:
        selected = DEFAULT_SELECTED_FEATURES.copy()
    # User-facing custom bot flow predates fine-grained feature selection.
    # Add Core and validate only the capabilities exposed by that flow.
    if "core" not in selected:
        selected.insert(0, "core")
    return _normalize_features(selected)


def create_custom_bot_request(user, token, features, bot_username=""):
    token = (token or "").strip()
    if not validate_bot_token(token):
        raise ValueError("invalid_token")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    owner = str(user.id)
    selected = normalize_features(features)
    row = sync_one("custom_bots", "owner_user_id=? AND bot_token=?", (owner, token))
    if row:
        sync_execute(
            "UPDATE custom_bots SET owner_name=?,owner_username=?,bot_username=?,features=?,status=?,pricing_plan=?,updated_at=? WHERE bot_key=?",
            (
                user.full_name or "",
                user.username or "",
                bot_username.strip().lstrip("@") or row.get("bot_username", ""),
                ",".join(selected),
                "active",
                "free_beta",
                now,
                row["bot_key"],
            ),
        )
        row = sync_one("custom_bots", "bot_key=?", (row["bot_key"],))
    else:
        key = f"custom_{owner}_{secrets.token_hex(3)}"
        sync_execute(
            "INSERT INTO custom_bots(bot_key,owner_user_id,owner_name,owner_username,bot_token,bot_username,features,status,pricing_plan,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                key,
                owner,
                user.full_name or "",
                user.username or "",
                token,
                bot_username.strip().lstrip("@"),
                ",".join(selected),
                "active",
                "free_beta",
                now,
                now,
            ),
        )
        row = sync_one("custom_bots", "bot_key=?", (key,))
    row["bot_token"] = ""
    return row
