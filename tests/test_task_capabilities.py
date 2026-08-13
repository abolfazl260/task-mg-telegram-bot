import asyncio
from types import SimpleNamespace

import pytest

from services.task_capabilities import (
    DEFAULT_TASK_OPTIONS,
    _sanitize_ai_draft,
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


def test_habit_profile_contains_expected_task_capabilities():
    import json
    from pathlib import Path

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


def test_main_routes_task_options_to_command_features():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert '"search": "allow_search"' in source
    assert '"templates": "allow_templates"' in source
    assert '"bulk_import": "allow_bulk_import"' in source
