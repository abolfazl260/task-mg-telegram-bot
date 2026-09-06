import handlers.habits as habits


def test_habit_menu_keyboard_has_expected_actions():
    keyboard = habits.habit_menu_keyboard()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "habit_create" in callbacks
    assert "habit_list" in callbacks
    assert "habit_today" in callbacks


def test_create_habit_keyboard_has_expected_actions():
    keyboard = habits.create_habit_keyboard()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "habit_template" in callbacks
    assert "habit_custom" in callbacks
    assert "habit_menu" in callbacks


def test_reminder_keyboard_has_expected_actions():
    keyboard = habits.reminder_keyboard()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "habit_reminder_none" in callbacks
    assert "habit_reminder_custom" in callbacks


def test_reminder_labels_are_defined():
    labels = habits.REMINDER_LABELS
    assert labels
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items())


def test_template_lookup_returns_template():
    template = habits.get_template("water")
    assert template["title"]
    assert template["category"]


def test_format_template_contains_template_fields():
    template = habits.get_template("water")
    text = habits.format_template(template)
    assert template["title"] in text
    assert template["category"] in text


def test_prepare_template_does_not_mutate_template():
    template = habits.get_template("water")
    original = dict(template)
    prepared = habits.prepare_template(template)
    assert template == original
    assert prepared["title"] == original["title"]


def test_template_form_keyboard_has_expected_actions():
    keyboard = habits.template_form_keyboard()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "habit_template_water" in callbacks
    assert "habit_template_medicine" in callbacks
    assert "habit_template_meditation" in callbacks


def test_format_habit_includes_status_and_statistics(monkeypatch):
    monkeypatch.setattr(habits, "stats_for_habit", lambda habit: {"current": 3, "best": 7, "total": 12, "last": "2026-09-07"})
    text = habits.format_habit({"title": "Reading", "category": "Learning", "repeat_type": "daily", "target": "30 minutes", "reminder_time": "09:00", "start_date": "2026-09-01", "active": "1"})
    assert "🌱 Reading" in text
    assert "📂 دسته‌بندی: Learning" in text
    assert "🔁 تکرار: روزانه" in text
    assert "🎯 هدف: 30 minutes" in text
    assert "⏰ یادآوری: روزانه ساعت 09:00" in text
    assert "📌 وضعیت: فعال" in text
    assert "🔥 زنجیره فعلی: 3 روز" in text
    assert "🏆 بهترین رکورد: 7 روز" in text
    assert "✅ تعداد انجام: 12 بار" in text
    assert "🕐 آخرین انجام: 2026-09-07" in text


def test_format_habit_includes_inactive_status():
    text = habits.format_habit({"title": "Reading", "repeat_type": "daily", "active": "0"})
    assert "📌 وضعیت: غیرفعال" in text


def test_habit_buttons_include_expected_actions():
    keyboard = habits.habit_buttons({"id": "h1", "active": "1"})
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert any("habit_done_h1" == callback for callback in callbacks)
