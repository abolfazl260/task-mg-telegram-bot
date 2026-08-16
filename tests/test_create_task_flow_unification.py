from types import SimpleNamespace

from handlers.tag_suggestions import _clear_create_task_state, _validate_create_task


def _valid_task():
    return {
        "title": "Prepare weekly report",
        "priority": "medium",
        "deadline": "",
        "category": "work",
        "tags": "report",
        "description": "Final version",
        "assignee": None,
    }


def test_valid_create_task_draft():
    assert _validate_create_task(_valid_task()) is None


def test_title_cannot_be_blank():
    task = _valid_task()
    task["title"] = "   "
    assert "عنوان" in _validate_create_task(task)


def test_title_max_length_is_enforced():
    task = _valid_task()
    task["title"] = "x" * 201
    assert "200" in _validate_create_task(task)


def test_priority_must_be_valid():
    task = _valid_task()
    task["priority"] = "urgent"
    assert "اولویت" in _validate_create_task(task)


def test_invalid_deadline_is_rejected():
    task = _valid_task()
    task["deadline"] = "not-a-date"
    assert "تاریخ" in _validate_create_task(task)


def test_optional_fields_may_be_empty():
    task = _valid_task()
    task.update({"deadline": "", "category": "", "tags": "", "description": ""})
    assert _validate_create_task(task) is None


def test_optional_field_limits_are_enforced():
    task = _valid_task()
    task["category"] = "x" * 31
    assert "دسته" in _validate_create_task(task)
    task = _valid_task()
    task["tags"] = "x" * 31
    assert "تگ" in _validate_create_task(task)


def test_create_task_state_cleanup_is_scoped():
    context = SimpleNamespace(
        user_data={
            "new_task": {"title": "draft"},
            "step": "description",
            "tag_suggestions": ["a"],
            "awaiting_tag_input": True,
            "created_task_id": "123",
            "_create_task_submitting": True,
            "ai_request_draft": {"title": "draft"},
            "unrelated_state": "keep",
        }
    )
    _clear_create_task_state(context)
    assert context.user_data["unrelated_state"] == "keep"
    assert "new_task" not in context.user_data
    assert "step" not in context.user_data
    assert "created_task_id" not in context.user_data
