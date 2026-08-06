"""Parse deadline strings in Gregorian or Jalali formats to YYYY-MM-DD."""

from datetime import datetime
import re
import jdatetime


def parse_deadline_input(text: str) -> str | None:
    """
    Accepts:
      - 2026-08-20 / 2026/08/20
      - 1405-05-29 / 1405/05/29 (Jalali)
    Returns ISO date YYYY-MM-DD or None if invalid.
    """

    if not text:
        return None

    s = text.strip().replace(".", "-").replace("/", "-")
    s = re.sub(r"\s+", "", s)

    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if not m:
        return None

    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))

    # Jalali years are typically 1300-1500 in practical use
    if 1300 <= y <= 1500:
        try:
            g = jdatetime.date(y, mo, d).togregorian()
            return g.isoformat()
        except Exception:
            return None

    try:
        return datetime(y, mo, d).date().isoformat()
    except Exception:
        return None
