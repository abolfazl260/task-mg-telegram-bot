from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_category_callbacks_are_short_indexes():
    source = read("handlers/task.py")
    # Category labels must never be embedded in callback_data because Telegram
    # limits callback_data to 64 UTF-8 bytes.
    assert "callback_data=f'category_pick_{index}'" in source or "callback_data=f\"category_pick_{index}\"" in source
    assert "cat[:40]" not in source


def test_category_handler_is_registered_for_category_pick():
    source = read("main.py")
    # Runtime routing uses numeric indexes: category_pick_0, category_pick_1, ...
    assert 'pattern="^(?:category_skip|category_pick_[0-9]+|tags_skip|description_skip)$"' in source


def test_category_flow_stores_selected_category_and_moves_to_tags():
    source = read("sitecustomize.py")
    assert "data.startswith(\"category_pick_\")" in source
    assert 'task["category"] = categories[index]' in source
    assert "await task_handler._ask_tags(query.message, context)" in source


def test_tag_suggestions_are_preserved_after_category_selection():
    source = read("handlers/tag_suggestions_legacy.py")
    assert 'task_module._ask_tags = ask_tags' in source
    assert 'recent_tag_keyboard(user_id, limit=3)' in source
    assert 'context.user_data["tag_suggestions"] = tags' in source
