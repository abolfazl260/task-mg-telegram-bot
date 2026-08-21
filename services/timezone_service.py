from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jdatetime

from services.user_service import get_user_date_format, get_user_date_format_async, get_user_timezone, get_user_timezone_async, set_user_timezone


# User-facing timezone choices. Values are IANA timezone identifiers.
TIMEZONE_CHOICES = (
    ("🇮🇷 ایران · تهران", "Asia/Tehran"),
    ("🇦🇫 افغانستان · کابل", "Asia/Kabul"),
    ("🇹🇯 تاجیکستان · دوشنبه", "Asia/Dushanbe"),
    ("🇦🇪 امارات · دبی", "Asia/Dubai"),
    ("🇹🇷 ترکیه · استانبول", "Europe/Istanbul"),
    ("🇷🇺 روسیه · مسکو", "Europe/Moscow"),
    ("🇷🇺 روسیه · سامارا", "Europe/Samara"),
    ("🇷🇺 روسیه · یکاترینبورگ", "Asia/Yekaterinburg"),
    ("🇷🇺 روسیه · نووسیبیرسک", "Asia/Novosibirsk"),
    ("🇩🇪 آلمان · برلین", "Europe/Berlin"),
    ("🇫🇷 فرانسه · پاریس", "Europe/Paris"),
    ("🇬🇧 بریتانیا · لندن", "Europe/London"),
    ("🇺🇸 آمریکا · نیویورک", "America/New_York"),
    ("🇺🇸 آمریکا · شیکاگو", "America/Chicago"),
    ("🇺🇸 آمریکا · دنور", "America/Denver"),
    ("🇺🇸 آمریکا · لس‌آنجلس", "America/Los_Angeles"),
    ("🇨🇦 کانادا · تورنتو", "America/Toronto"),
    ("🇨🇦 کانادا · ونکوور", "America/Vancouver"),
    ("🇦🇺 استرالیا · سیدنی", "Australia/Sydney"),
    ("🇯🇵 ژاپن · توکیو", "Asia/Tokyo"),
    ("🇰🇷 کره جنوبی · سئول", "Asia/Seoul"),
    ("🇮🇳 هند · دهلی", "Asia/Kolkata"),
)

VALID_TIMEZONES = frozenset(tz_name for _, tz_name in TIMEZONE_CHOICES)


def is_valid_timezone(tz_name: str) -> bool:
    """Return whether an IANA timezone identifier is valid."""
    tz_name = (tz_name or "").strip()
    if not tz_name:
        return False
    if tz_name in VALID_TIMEZONES:
        return True
    try:
        ZoneInfo(tz_name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def get_current_local_datetime(user_id) -> tuple[str, datetime]:
    """Return the user's timezone name and current timezone-aware datetime."""
    timezone_name = get_user_timezone(user_id)
    try:
        return timezone_name, datetime.now(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC", datetime.now(ZoneInfo("UTC"))


async def get_current_local_datetime_async(user_id) -> tuple[str, datetime]:
    """Async equivalent used by Telegram handlers running inside the event loop."""
    timezone_name = await get_user_timezone_async(user_id)
    try:
        return timezone_name, datetime.now(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC", datetime.now(ZoneInfo("UTC"))


def build_timezone_text(user_id) -> str:
    timezone_name, now = get_current_local_datetime(user_id)
    date_format = get_user_date_format(user_id)
    if date_format == "gregorian":
        display_date = now.strftime("%Y/%m/%d")
    else:
        display_date = jdatetime.date.fromgregorian(date=now.date()).strftime("%Y/%m/%d")
    return (
        "🌍 **زمان محلی**\n\n"
        f"🕐 ساعت فعلی: **{now:%H:%M:%S}**\n"
        f"📅 تاریخ: **{display_date}**\n"
        f"📍 منطقه زمانی: `{timezone_name}`\n\n"
        "منطقه زمانی موردنظر خود را انتخاب کنید:"
    )


def build_timezone_keyboard(user_id, button_factory) -> list[list]:
    """Build timezone rows using the caller's Telegram button factory."""
    current = get_user_timezone(user_id)
    rows = []
    for label, tz_name in TIMEZONE_CHOICES:
        selected = " ✅" if tz_name == current else ""
        rows.append([
            button_factory(
                f"{label}{selected}",
                callback_data=f"timezone_set_{tz_name}",
            )
        ])
    return rows


__all__ = [
    "TIMEZONE_CHOICES",
    "VALID_TIMEZONES",
    "build_timezone_keyboard",
    "build_timezone_text",
    "get_current_local_datetime",
    "get_current_local_datetime_async",
    "get_user_timezone",
    "is_valid_timezone",
    "set_user_timezone",
]
