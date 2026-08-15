from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_start_command_is_registered():
    main = read("main.py")
    assert 'CommandHandler("start", start)' in main


def test_add_command_is_registered():
    main = read("main.py")
    assert 'CommandHandler("add", add_task)' in main


def test_priority_callbacks_are_routed():
    main = read("main.py")
    task = read("handlers/task.py")
    assert "priority_high" in main
    assert "priority_medium" in main
    assert "priority_low" in main
    assert "priority_selected" in task


def test_timezone_callback_is_routed_and_persisted():
    menu = read("handlers/menu.py")
    user_service = read("services/user_service.py")
    assert 'data.startswith("timezone_set_")' in menu
    assert "set_user_timezone" in menu
    assert 'DEFAULT_TIMEZONE = "Asia/Tehran"' in user_service


def test_category_flow_uses_short_callback_ids():
    sitecustomize = read("sitecustomize.py")
    category_flow = read("handlers/category_flow.py")
    main = read("main.py")
    assert 'callback_data=f"category_pick_{index}"' in sitecustomize
    assert 'callback_data=f"category_pick_{category_key(category)}"' in category_flow
    assert 'CallbackQueryHandler(optional_field_callback' in main
    assert 'category_pick_' in main
    assert 'CallbackQueryHandler.__init__' in sitecustomize


def test_task_creation_has_shared_manual_flow_entry_points():
    main = read("main.py")
    menu = read("handlers/menu.py")
    assert 'CommandHandler("add", add_task)' in main
    assert 'callback_data="add_task_manual"' in menu
    assert 'context.user_data["step"] = "title"' in menu
