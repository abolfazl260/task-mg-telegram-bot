from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_tag_callback_pattern_matches_real_callbacks():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    match = re.search(
        r'CallbackQueryHandler\(handle_tag_callback,\s*pattern="([^"]+)"\)',
        source,
    )
    assert match, "Tag callback handler is not registered"
    pattern = match.group(1)
    matcher = re.compile(pattern)
    for callback_data in (
        "tag_new",
        "tag_pick_0",
        "tag_pick_12",
        "tag_none",
        "tags_skip",
        "step_back_category",
        "step_back_description",
    ):
        assert matcher.match(callback_data), callback_data


def test_generic_callback_handler_excludes_tag_callbacks():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "|tag_|tags_|step_back_description|step_back_category|" in source


def test_tag_keyboard_contains_required_callbacks_and_no_csv_dependency():
    source = (ROOT / "utils" / "keyboard.py").read_text(encoding="utf-8")
    for callback_data in (
        'callback_data="tag_new"',
        'callback_data="tag_none"',
        'callback_data="step_back_category"',
        'callback_data=f"tag_pick_{index + offset}"',
    ):
        assert callback_data in source
    assert "csv" not in source.lower()


def test_tag_suggestions_use_existing_tasks_table_and_no_tag_table():
    keyboard_source = (ROOT / "utils" / "keyboard.py").read_text(encoding="utf-8")
    db_source = (ROOT / "services" / "database.py").read_text(encoding="utf-8")
    assert "FROM tasks" in keyboard_source
    assert "bot_key = ?" in keyboard_source
    assert "user_id = ?" in keyboard_source
    assert "tags" in db_source
    assert "CREATE TABLE IF NOT EXISTS tags" not in db_source
    assert "csv" not in keyboard_source.lower()


def test_tag_text_flow_sets_tag_and_moves_to_description():
    source = (ROOT / "handlers" / "tag_suggestions.py").read_text(encoding="utf-8")
    assert 'context.user_data.get("step") != "tags"' in source
    assert 'task["tags"] = text[:120]' in source
    assert 'await task_module._ask_description(update.effective_message, context)' in source
