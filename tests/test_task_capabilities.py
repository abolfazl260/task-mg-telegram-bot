from pathlib import Path
from types import SimpleNamespace

import pytest

from services.task_capabilities import (
    DEFAULT_TASK_OPTIONS,
    _sanitize_ai_draft,
    install_task_capabilities,
    task_option_enabled,
    task_options,
    wrap_callback,
)


class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.answers = []

    async def answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))


class DummyContext:
    def __init__(self, options=None):
        profile = SimpleNamespace(settings={"task_options": options or {}})
        self.bot_data = {"bot_config": profile}
        self.user_data = {}


class DummyUpdate:
    def __init__(self, data):
        self.callback_query = DummyQuery(data)


def test_default_task_options_are_enabled():
    assert all(DEFAULT_TASK_OPTIONS.values())
    assert task_options(None) == DEFAULT_TASK_OPTIONS


def test_profile_overrides_only_known_task_options():
    profile = SimpleNamespace(settings={"task_options": {"allow_tags": False, "unknown": False}})
    result = task_options(profile)
    assert result["allow_tags"] is False
    assert "unknown" not in result
    assert result["allow_comments"] is True


def test_task_option_enabled_reads_active_profile():
    context = DummyContext({"allow_assignment": False})
    assert task_option_enabled(context, "allow_assignment") is False
    assert task_option_enabled(context, "allow_comments") is True


def test_ai_draft_is_sanitized_for_disabled_capabilities():
    context = DummyContext({
        "allow_assignment": False,
        "allow_tags": False,
        "allow_categories": False,
    })
    draft = {
        "title": "Test",
        "tags": "private",
        "category": "work",
        "assignee": {"user_id": "123"},
        "team_id": "team-1",
    }
    result = _sanitize_ai_draft(context, draft)
    assert result["tags"] == ""
    assert result["category"] == ""
    assert result["assignee"] is None
    assert result["team_id"] == ""
    assert result["title"] == "Test"


@pytest.mark.asyncio
async def test_assignment_callback_is_blocked_when_disabled():
    called = False

    async def original(update, context):
        nonlocal called
        called = True

    wrapped = wrap_callback(original)
    context = DummyContext({"allow_assignment": False})
    update = DummyUpdate("assign_self_123")

    await wrapped(update, context)

    assert called is False
    assert update.callback_query.answers
    assert update.callback_query.answers[0][1]["show_alert"] is True


@pytest.mark.asyncio
async def test_comments_are_blocked_when_disabled():
    called = False

    async def original(update, context):
        nonlocal called
        called = True

    wrapped = wrap_callback(original)
    context = DummyContext({"allow_comments": False})
    update = DummyUpdate("comment_add_123")

    await wrapped(update, context)

    assert called is False
    assert update.callback_query.answers


@pytest.mark.asyncio
async def test_tags_are_blocked_when_disabled():
    called = False

    async def original(update, context):
        nonlocal called
        called = True

    wrapped = wrap_callback(original)
    context = DummyContext({"allow_tags": False})
    update = DummyUpdate("tag_new")

    await wrapped(update, context)

    assert called is False
    assert update.callback_query.answers


@pytest.mark.asyncio
async def test_templates_and_bulk_import_callbacks_are_blocked_when_disabled():
    for callback_data in ("template_open", "import_bulk"):
        called = False

        async def original(update, context):
            nonlocal called
            called = True

        wrapped = wrap_callback(original)
        context = DummyContext({"allow_templates": False, "allow_bulk_import": False})
        update = DummyUpdate(callback_data)

        await wrapped(update, context)

        assert called is False
        assert update.callback_query.answers


@pytest.mark.asyncio
async def test_ai_task_creation_is_blocked_when_disabled():
    called = False

    async def original(update, context):
        nonlocal called
        called = True

    wrapped = wrap_callback(original)
    context = DummyContext({"allow_ai_task_creation": False})
    update = DummyUpdate("ai_task_create")

    await wrapped(update, context)

    assert called is False
    assert update.callback_query.answers


def test_install_task_capabilities_is_idempotent_and_application_scoped():
    async def assignment_callback(update, context):
        return None

    handler = SimpleNamespace(callback=assignment_callback)
    app = SimpleNamespace(handlers={0: [handler]})

    install_task_capabilities(app)
    first = handler.callback
    install_task_capabilities(app)

    assert getattr(app, "_task_capabilities_installed", False) is True
    assert first is handler.callback
    assert getattr(first, "_task_capability_wrapped", False) is True


def test_habit_profile_contains_expected_task_capabilities():
    import json

    path = Path(__file__).resolve().parents[1] / "bots" / "habits_only.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    options = profile["settings"]["task_options"]
    assert options == {
        "allow_assignment": False,
        "allow_tags": False,
        "allow_comments": True,
        "allow_categories": True,
        "allow_search": True,
        "allow_templates": False,
        "allow_bulk_import": False,
        "allow_ai_task_creation": True,
    }


def test_add_flow_and_commands_respect_capabilities():
    root = Path(__file__).resolve().parents[1]
    tag_source = (root / "handlers" / "tag_suggestions.py").read_text(encoding="utf-8")
    main_source = (root / "main.py").read_text(encoding="utf-8")
    assert 'task_option_enabled(context, "allow_bulk_import")' in tag_source
    assert 'task_option_enabled(context, "allow_ai_task_creation")' in tag_source
    assert '"search": "allow_search"' in main_source
    assert '"templates": "allow_templates"' in main_source
    assert '"bulk_import": "allow_bulk_import"' in main_source
    assert "install_task_capabilities(app)" in main_source


def test_no_global_application_add_handler_monkeypatch():
    source = (Path(__file__).resolve().parents[1] / "bot_platform.py").read_text(encoding="utf-8")
    assert "Application.add_handler =" not in source
