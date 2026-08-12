import json

import pytest

from services import groq_service


@pytest.mark.parametrize(
    ("message", "expected_repeat", "expected_reminder"),
    [
        ("هر روز ساعت ۸ صبح ورزش کنم", "daily", "08:00"),
        ("هر روز ساعت ۸ و ۱۴ آب بخورم", "daily", "08:00,14:00"),
        ("هر هفته سه بار ورزش کنم", "weekly", ""),
        ("هر ماه گزارش مالی را بررسی کنم", "monthly", ""),
    ],
)
def test_parse_recurring_request_as_habit(monkeypatch, message, expected_repeat, expected_reminder):
    payload = {
        "action": "CREATE_HABIT",
        "title": "ورزش" if "ورزش" in message else "آب خوردن" if "آب" in message else "گزارش مالی",
        "repeat_type": expected_repeat,
        "reminder_time": expected_reminder,
        "target": "سه بار در هفته" if "سه بار" in message else "",
        "priority": "medium",
        "category": "",
        "tags": "",
        "description": "",
        "deadline": "",
    }
    monkeypatch.setattr(groq_service, "_groq_request", lambda prompt: json.dumps(payload, ensure_ascii=False))

    draft = groq_service.parse_task_request(123, message)

    assert draft["action"] == "CREATE_HABIT"
    assert draft["repeat_type"] == expected_repeat
    assert draft["reminder_time"] == expected_reminder
    assert draft["deadline"] == ""


def test_one_time_request_stays_task(monkeypatch):
    payload = {
        "action": "CREATE_TASK",
        "title": "جلسه با مدیران خودرو",
        "deadline": "2026-08-12 14:00",
        "priority": "medium",
        "category": "",
        "tags": "",
        "description": "",
        "repeat_type": "",
        "target": "",
        "reminder_time": "",
    }
    monkeypatch.setattr(groq_service, "_groq_request", lambda prompt: json.dumps(payload, ensure_ascii=False))

    draft = groq_service.parse_task_request(123, "امروز ساعت ۲ جلسه با مدیران خودرو دارم")

    assert draft["action"] == "CREATE_TASK"
    assert draft["deadline"] == "2026-08-12 14:00"
    assert draft["repeat_type"] == ""
