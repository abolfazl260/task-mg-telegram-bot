"""Persistent user support tickets and administrator notifications."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from services.database import execute, fetch_one
from services.admin_service import notify_admins


async def ensure_support_schema() -> None:
    await execute("""CREATE TABLE IF NOT EXISTS support_tickets (
        ticket_id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default',
        user_id TEXT NOT NULL, username TEXT NOT NULL DEFAULT '',
        full_name TEXT NOT NULL DEFAULT '', message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    await execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(bot_key,user_id,created_at)")


def _ticket_id() -> str:
    return f"SUP-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"


async def create_support_ticket(user, message: str, bot_key: str = "default", context=None) -> str:
    await ensure_support_schema()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ticket_id = _ticket_id()
    await execute(
        "INSERT INTO support_tickets(ticket_id,bot_key,user_id,username,full_name,message,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (ticket_id, bot_key, str(user.id), user.username or "", user.full_name or "", message, now, now),
    )
    await notify_admins(context, f"🎫 تیکت جدید {ticket_id}\n\nکاربر: {user.full_name}\nیوزرنیم: @{user.username or '—'}\nآیدی: {user.id}\n\n{message}")
    return ticket_id


async def get_support_ticket(ticket_id: str):
    await ensure_support_schema()
    return await fetch_one("support_tickets", "ticket_id=?", (ticket_id,))
