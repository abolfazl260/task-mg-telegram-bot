from datetime import date

import jdatetime
import pytest

from services import date_service
from utils.date_parse import parse_deadline_input


def test_jalali_and_gregorian_formatting():
    value = date(2026, 8, 20)
    assert date_service.format_date(value, "gregorian") == "2026/08/20"
    assert date_service.format_date(value, "jalali") == jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-08-20", "2026-08-20"),
        ("2026/08/20", "2026-08-20"),
        ("1405-05-29", jdatetime.date(1405, 5, 29).togregorian().isoformat()),
    ],
)
def test_parser_accepts_calendar_inputs(value, expected):
    assert parse_deadline_input(value) == expected


@pytest.mark.parametrize("value", ["", "not-a-date", "1404-13-01", "2026-02-30"])
def test_invalid_date_input_returns_none(value):
    assert parse_deadline_input(value) is None


def test_jalali_boundary_years_and_month_boundary():
    assert jdatetime.date(1400, 1, 1).togregorian() == date(2021, 3, 21)
    assert jdatetime.date(1405, 1, 1).togregorian() == date(2026, 3, 21)
    start = jdatetime.date(1405, 12, 1).togregorian()
    end = jdatetime.date(1406, 1, 1).togregorian()
    assert start == date(2027, 2, 20)
    assert end == date(2027, 3, 21)
