"""Centralized user calendar/date utilities.

Storage/query dates remain Gregorian ISO (YYYY-MM-DD). This module only
controls user-facing calendar conversion and calendar-boundary calculations.
"""

from datetime import date, datetime, timedelta

import jdatetime

from services.timezone_service import get_current_local_datetime
from services.user_service import get_user_date_format

VALID_DATE_FORMATS = frozenset(("jalali", "gregorian"))
DEFAULT_DATE_FORMAT = "jalali"


def normalize_date_format(value: str | None) -> str:
    value = (value or DEFAULT_DATE_FORMAT).strip().lower()
    return value if value in VALID_DATE_FORMATS else DEFAULT_DATE_FORMAT


def get_user_date_format_for_display(user_id) -> str:
    return normalize_date_format(get_user_date_format(user_id))


def to_gregorian_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def format_date(value, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    """Format a Gregorian date for display; never mutate stored data."""
    d = to_gregorian_date(value)
    if d is None:
        return "—"
    if normalize_date_format(date_format) == "gregorian":
        return d.strftime("%Y/%m/%d")
    return jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")


def format_datetime(value, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text[:19], fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return str(value)
    return f"{format_date(dt.date(), date_format)} {dt:%H:%M}" if " " in str(value).strip() else format_date(dt.date(), date_format)


def user_today(user_id) -> date:
    """Return today's Gregorian date according to the user's timezone."""
    _, now = get_current_local_datetime(user_id)
    return now.date()


def selected_calendar_today(user_id):
    """Return (calendar-year, calendar-month, calendar-day) for the user."""
    today = user_today(user_id)
    if get_user_date_format_for_display(user_id) == "gregorian":
        return today.year, today.month, today.day
    j = jdatetime.date.fromgregorian(date=today)
    return j.year, j.month, j.day


def calendar_month_bounds(user_id, year: int | None = None, month: int | None = None):
    """Return Gregorian start/end dates for the selected user's calendar month."""
    date_format = get_user_date_format_for_display(user_id)
    if year is None or month is None:
        year, month, _ = selected_calendar_today(user_id)

    if date_format == "gregorian":
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return start, end

    start_j = jdatetime.date(year, month, 1)
    if month == 12:
        next_j = jdatetime.date(year + 1, 1, 1)
    else:
        next_j = jdatetime.date(year, month + 1, 1)
    return start_j.togregorian(), (next_j - jdatetime.timedelta(days=1)).togregorian()


def current_month_bounds(user_id):
    return calendar_month_bounds(user_id)


def add_gregorian_days(days: int, user_id=None) -> date:
    """Calculate quick deadline buttons in Gregorian internally."""
    base = user_today(user_id) if user_id is not None else date.today()
    return base + timedelta(days=int(days))


__all__ = [
    "DEFAULT_DATE_FORMAT",
    "VALID_DATE_FORMATS",
    "add_gregorian_days",
    "calendar_month_bounds",
    "current_month_bounds",
    "format_date",
    "format_datetime",
    "get_user_date_format_for_display",
    "normalize_date_format",
    "selected_calendar_today",
    "to_gregorian_date",
    "user_today",
]
