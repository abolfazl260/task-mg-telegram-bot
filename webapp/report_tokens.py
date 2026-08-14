"""Opaque, non-guessable tokens for sharing private web reports."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from services.database import sync_execute, sync_one

TOKEN_BYTES = 32
DEFAULT_TTL_DAYS = 30


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_report_token_table() -> None:
    sync_execute(
        """CREATE TABLE IF NOT EXISTS web_report_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            bot_key TEXT NOT NULL,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            report_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )"""
    )
    sync_execute(
        "CREATE INDEX IF NOT EXISTS idx_web_report_tokens_lookup ON web_report_tokens(token_hash, revoked, expires_at)"
    )
    sync_execute(
        "CREATE INDEX IF NOT EXISTS idx_web_report_tokens_owner ON web_report_tokens(bot_key, user_id, report_type)"
    )


def create_report_token(bot_key: str, user_id: str, report_type: str = "monthly", ttl_days: int = DEFAULT_TTL_DAYS) -> str:
    ensure_report_token_table()
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)
    sync_execute(
        "INSERT INTO web_report_tokens(token_hash,bot_key,user_id,report_type,created_at,expires_at) VALUES(?,?,?,?,?,?)",
        (_hash(raw), str(bot_key), str(user_id), str(report_type), now.isoformat(), expires.isoformat()),
    )
    return raw


def resolve_report_token(token: str) -> dict | None:
    if not token or len(token) < 40:
        return None
    ensure_report_token_table()
    row = sync_one(
        "web_report_tokens",
        "token_hash=? AND revoked=0 AND expires_at>?",
        (_hash(token), datetime.now(timezone.utc).isoformat()),
    )
    return row


def revoke_report_token(token: str) -> None:
    if not token:
        return
    ensure_report_token_table()
    sync_execute("UPDATE web_report_tokens SET revoked=1 WHERE token_hash=?", (_hash(token),))


def build_report_url(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/report/{quote(token, safe='')}"
