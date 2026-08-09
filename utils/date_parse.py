"""Parse deadline strings in Gregorian or Jalali formats to YYYY-MM-DD."""

from datetime import datetime
import re
import jdatetime


def parse_deadline_input(text: str, date_format: str | None = None) -> str | None:
    """
    Accept both calendars and always return internal Gregorian ISO YYYY-MM-DD.

    date_format is only a hint for the preferred calendar; both formats remain
    accepted for backwards compatibility.
    """
    if not text:
        return None

    s = text.strip().replace(".", "-").replace("/", "-")
    s = re.sub(r"\s+", "", s)

    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if not m:
        return None

    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))

    # Jalali years are typically 1300-1500 in practical use.
    if 1300 <= y <= 1500:
        try:
            return jdatetime.date(y, mo, d).togregorian().isoformat()
        except Exception:
            return None

    try:
        return datetime(y, mo, d).date().isoformat()
    except Exception:
        return None


def deadline_input_hint(date_format: str = "jalali") -> str:
    """Return the user-facing preferred deadline example."""
    if (date_format or "jalali").lower() == "gregorian":
        return "مثال: `2026-08-20`"
    return "مثال: `1405-05-29`"
