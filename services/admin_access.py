"""Short-lived admin backoffice links."""
from __future__ import annotations
import hashlib, secrets, time
from urllib.parse import quote
from services.database import sync_execute, fetch_one, _run
from webapp.config import WEBAPP_BASE_URL

TTL_SECONDS = 600
def _hash(token: str) -> str: return hashlib.sha256(token.encode()).hexdigest()
def _ensure():
    sync_execute("""CREATE TABLE IF NOT EXISTS admin_access_tokens (
        token_hash TEXT PRIMARY KEY, admin_id TEXT NOT NULL, created_at REAL NOT NULL,
        expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)""")
def create_admin_link(admin_id: object) -> str:
    _ensure(); token = secrets.token_urlsafe(32); now = time.time()
    sync_execute("INSERT INTO admin_access_tokens(token_hash,admin_id,created_at,expires_at) VALUES(?,?,?,?)", (_hash(token), str(admin_id), now, now + TTL_SECONDS))
    return f"{WEBAPP_BASE_URL}/backoffice/{quote(token, safe='')}"
def resolve_admin_token(token: str) -> str | None:
    if not token: return None
    _ensure(); row = _run(fetch_one("admin_access_tokens", "token_hash=? AND revoked=0 AND expires_at>?", (_hash(token), time.time())))
    return str(row.get("admin_id")) if row else None
