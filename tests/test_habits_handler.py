from datetime import date

from handlers import habits


def test_habit_menu_contains_all_primary_actions():
    keyboard = habits.habit_menu_keyboard()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["habit_create", "habit_list", "habit_today", "habit_records", "habit_dashboard", "habit_reminders"]


def test_create_keyboard_contains_new_template_and_back_actions():
    keyboard = habits._create_keyboard()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["habit_new", "habit_templates", "habit_list"]


def test_reminder_keyboard_contains_supported_times_and_disable_option():
    keyboard = habits._reminder_keyboard("abc123")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "habit_remtime_abc123_07:00" in callbacks
    assert "habit_remtime_abc123_09:00" in callbacks
    assert "habit_remtime_abc123_11:00" in callbacks
    assert "habit_remtime_abc123_18:00" in callbacks
    assert "habit_remtime_abc123_21:00" in callbacks
    assert "habit_remtime_abc123_none" in callbacks
    assert "habit_list" in callbacks


def test_reminder_label_handles_none_single_multiple_and_repeat_types():
    assert habits.reminder_label({"reminder_time": ""}) == "بدون یادآوری"
    assert habits.reminder_label({"reminder_time": "09:00", "repeat_type": "daily"}) == "روزانه ساعت 09:00"
    assert habits.reminder_label({"reminder_time": "09:00", "repeat_type": "weekly"}) == "هفتگی در روز شروع عادت، ساعت 09:00"
    assert habits.reminder_label({"reminder_time": "09:00", "repeat_type": "monthly"}) == "ماهانه در تاریخ روز شروع عادت، ساعت 09:00"
    assert habits.reminder_label({"reminder_time": "09:00, 18:00", "repeat_type": "daily"}) == "روزانه در ساعت‌های 09:00, 18:00"


def test_find_template_returns_existing_and_none_for_unknown():
    template = habits._find_template("water")
    assert template is not None
    assert template["key"] == "water"
    assert habits._find_template("does-not-exist") is None


def test_format_template_contains_user_relevant_details():
    template = habits._find_template("water")
    text = habits.format_template(template)
    assert template["title"] in text
    assert "🎯 هدف:" in text
    assert "📌 نوع:" in text
    assert "🔢 مقدار:" in text
    assert "📏 واحد:" in text
    assert "🔁 تکرار:" in text
    assert "⏰ یادآوری:" in text
    assert template["description"] in text


def test_prepare_template_creates_editable_draft():
    class Context:
        user_data = {}
    context = Context()
    template = habits._find_template("medicine")
    habits._prepare_template(context, template)
    draft = context.user_data["new_habit"]
    assert draft["template_key"] == "medicine"
    assert draft["title"] == template["title"]
    assert draft["repeat_type"] == "daily"
    assert draft["reminder_time"] == "09:00,21:00"
    assert draft["reminder_time_display"] == "09:00، 21:00"
    assert draft["start_date"] == date.today().isoformat()
    assert context.user_data["habit_step"] is None


def test_prepare_template_does_not_mutate_template_reminders():
    class Context:
        user_data = {}
    context = Context()
    template = habits._find_template("water")
    original_times = list(template["reminder_times"])
    habits._prepare_template(context, template)
    context.user_data["new_habit"]["reminder_time"] = "22:00"
    assert template["reminder_times"] == original_times


def test_template_form_keyboard_exposes_edit_and_confirm_actions():
    keyboard = habits._template_form_keyboard("reading")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["habit_tpl_target_reading", "habit_tpl_rem_reading", "habit_tpl_date_reading", "habit_tpl_confirm_reading", "habit_templates"]


def test_format_habit_includes_status_and_statistics(monkeypatch):
    monkeypatch.setattr(habits, "stats_for_habit", lambda habit: {"current": 3, "best": 7, "total": 12, "last": "2026-09-07"})
    text = habits.format_habit({"title": "Reading", "category": "Learning", "repeat_type": "daily", "target": "30 minutes", "reminder_time": "09:00", "start_date": "2026-09-01", "active": 1})
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


def test_format_habit_marks_inactive_habit(monkeypatch):
    monkeypatch.setattr(habits, "stats_for_habit", lambda habit: {"current": 0, "best": 0, "total": 0, "last": "—"})
    text = habits.format_habit({"title": "A", "active": 0, "repeat_type": "daily"})
    assert "📌 وضعیت: غیرفعال" in text
    assert "⏰ یادآوری: بدون یادآوری" in text


def test_habit_buttons_use_expected_prefix_and_ids():
    items = [{"id": "one", "title": "First"}, {"id": "two", "title": "Second"}]
    keyboard = habits._habit_buttons(items, "habit_done")
    assert [[b.callback_data for b in row] for row in keyboard.inline_keyboard] == [["habit_done_one"], ["habit_done_two"]]
    assert [b.text for row in keyboard.inline_keyboard for b in row] == ["First", "Second"]
