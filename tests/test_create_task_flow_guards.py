from handlers.create_task_flow import add_create_cancel, clear_create_task_state, validate_create_task_draft


def test_validate_create_task_draft():
    assert validate_create_task_draft({"title": "Task", "priority": "high"}) is None
    assert validate_create_task_draft({"title": "   ", "priority": "high"})
    assert validate_create_task_draft({"title": "Task", "priority": "invalid"})
    assert validate_create_task_draft({"title": "x" * 201, "priority": "high"})


def test_add_create_cancel_is_idempotent():
    markup = add_create_cancel(add_create_cancel(__import__("telegram").InlineKeyboardMarkup([])))
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert callbacks.count("assign_cancel_create") == 1


def test_clear_create_task_state_preserves_unrelated_state():
    class Context:
        user_data = {
            "new_task": {"title": "draft"},
            "step": "description",
            "tag_suggestions": ["bug"],
            "awaiting_tag_input": True,
            "create_task_finalizing": True,
            "unrelated": "keep",
        }

    clear_create_task_state(Context())
    assert Context.user_data == {"unrelated": "keep"}
