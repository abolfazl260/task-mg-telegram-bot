"""Shared Telegram date choices used by task and Clinic flows."""
from datetime import datetime, timedelta, timezone

import jdatetime


def deadline_label(days: int, today=None) -> str:
    target = (today or datetime.now(timezone.utc).date()) + timedelta(days=days)
    jalali = jdatetime.date.fromgregorian(date=target).strftime("%Y/%m/%d")
    prefix = "امروز" if days == 0 else "فردا" if days == 1 else f"{days} روز بعد"
    return f"{prefix} · {jalali}"


def deadline_value(days: int, today=None) -> str:
    return ((today or datetime.now(timezone.utc).date()) + timedelta(days=days)).isoformat()
