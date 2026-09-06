import handlers.habits as habits


def _callbacks(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_habit_menu_keyboard_has_expected_actions():
    keyboard = habits.habit_menu_keyboard()
    callbacks = _callbacks(keyboard)
    assert "habit_create" in callbacks
    assert "habit_list" in callbacks
    assert "habit_today" in callbacks
    assert "habit_records" in callbacks
    assert "habit_dashboard" in callbacks
    assert "habit_reminders" in callbacks


def test_create_keyboard_has_expected_actions():
    keyboard = habits._create_keyboard()
    callbacks = _callbacks(keyboard)
    assert "habit_new" in callbacks
    assert "habit_templates" in callbacks
    assert "habit_list" in callbacks


def test_reminder_keyboard_has_expected_actions():
    keyboard = habits._reminder_keyboard("h1")
    callbacks = _callbacks(keyboard)
    assert "habit_remtime_h1_07:00" in callbacks
    assert "habit_remtime_h1_09:00" in callbacks
    assert "habit_remtime_h1_21:00" in callbacks
    assert "habit_remtime_h1_none" in callbacks
    assert "habit_list" in callbacks


def test_reminder_label_handles_supported_repeat_types():
    assert habits.reminder_label({"repeat_type": "daily", "reminder_time": "09:00"}) == "روزانه ساعت 09:00"
    assert habits.reminder_label({"repeat_type": "weekly", "reminder_time": "09:00"}) == "هفتگی در روز شروع عادت، ساعت 09:00"
    assert habits.reminder_label({"repeat_type": "monthly", "reminder_time": "09:00"}) == "ماهانه در تاریخ روز شروع عادت، ساعت 09:00"
    assert habits.reminder_label({"repeat_type": "daily", "reminder_time": ""}) == "بدون یادآوری"


def test_template_lookup_returns_template():
    template = habits._find_template("water")
    assert template is not None
    assert template["title"]
    assert template["category"]


def test_template_lookup_missing_returns_none():
    assert habits._find_template("missing") is None


def test_format_template_contains_template_fields():
    template = habits._find_template("water")
    text = habits.format_template(template)
    assert template["title"] in text
    assert template["description"] in text
    assert "🎯 هدف:" in text
    assert "🔁 تکرار:" in text
    assert "⏰ یادآوری:" in text


def test_prepare_template_does_not_mutate_template():
    template = habits._find_template("water")
    original = dict(template)
    context = type("Context", (), {"user_data": {}})()
    habits._prepare_template(context, template)
    assert template == original
    assert context.user_data["new_habit"]["title"] == original["title"]
    assert context.user_data["new_habit"]["template_key"] == "water"


def test_template_form_keyboard_has_expected_actions():
    keyboard = habits._template_form_keyboard("water")
    callbacks = _callbacks(keyboard)
    assert "habit_tpl_target_water" in callbacks
    assert "habit_tpl_rem_water" in callbacks
    assert "habit_tpl_date_water" in callbacks
    assert "habit_tpl_confirm_water" in callbacks
    assert "habit_templates" in callbacks


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
    keyboard = habits._habit_buttons([{"id": "h1", "title": "Reading"}], "habit_done")
    callbacks = _callbacks(keyboard)
    assert callbacks == ["habit_done_h1"]
