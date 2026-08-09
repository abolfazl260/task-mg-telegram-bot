from datetime import date

import jdatetime

from services import date_service
from services import user_service
from utils.date_parse import parse_deadline_input


def _configure_users(tmp_path, monkeypatch):
    path = tmp_path / "users.csv"
    monkeypatch.setattr(user_service, "FILE_PATH", str(path))
    user_service.init_users()
    return path


def test_jalali_and_gregorian_formatting():
    value = date(2026, 8, 20)
    assert date_service.format_date(value, "gregorian") == "2026/08/20"
    assert date_service.format_date(value, "jalali") == jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")


def test_parser_accepts_both_calendars_and_stores_gregorian():
    assert parse_deadline_input("2026-08-20") == "2026-08-20"
    assert parse_deadline_input("1405-05-29") == jdatetime.date(1405, 5, 29).togregorian().isoformat()


def test_new_user_defaults_to_jalali(tmp_path, monkeypatch):
    _configure_users(tmp_path, monkeypatch)

    class User:
        id = 123
        full_name = "Test"
        username = "test"

    user_service.record_user(User(), increment_usage=False)
    assert user_service.get_user_date_format(123) == "jalali"


def test_change_date_format_does_not_change_stored_data(tmp_path, monkeypatch):
    path = _configure_users(tmp_path, monkeypatch)

    class User:
        id = 123
        full_name = "Test"
        username = "test"

    user_service.record_user(User(), increment_usage=False)
    assert user_service.set_user_date_format(123, "gregorian")
    assert user_service.get_user_date_format(123) == "gregorian"

    rows = user_service.read_users()
    assert rows[0]["date_format"] == "gregorian"
    assert rows[0]["timezone"] == "UTC"
    assert rows[0]["first_seen"]
    assert path.exists()


def test_jalali_month_boundary_maps_to_gregorian():
    start = jdatetime.date(1405, 1, 1).togregorian()
    next_month = jdatetime.date(1405, 2, 1).togregorian()
    end = next_month.fromordinal(next_month.toordinal() - 1)
    assert start == date(2026, 3, 21)
    assert end == date(2026, 4, 20)
