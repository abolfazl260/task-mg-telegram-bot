from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import CommandHandler, ConversationHandler

from bot_platform import BotProfile, DEFAULT_FEATURES


@pytest.fixture
def app_main():
    task_handler = importlib.import_module("handlers.task")
    reports_handler = importlib.import_module("handlers.reports")
    extra_reports_handler = importlib.import_module("handlers.extra_reports")
    targets = [
        (task_handler, "format_task_card"),
        (task_handler, "build_full_report"),
        (reports_handler, "report_all_tasks"),
        (reports_handler, "report_by_priority"),
        (reports_handler, "report_stuck"),
        (reports_handler, "report_trend"),
        (reports_handler, "report_calendar"),
        (reports_handler, "report_week"),
        (reports_handler, "report_heatmap"),
        (reports_handler, "report_heatmap_week"),
        (reports_handler, "report_today"),
        (reports_handler, "reports_menu_keyboard"),
        (extra_reports_handler, "report_compare_months"),
    ]
    originals = [(module, name, getattr(module, name)) for module, name in targets]
    module = importlib.import_module("main")
    try:
        yield module
    finally:
        for target_module, name, original in originals:
            setattr(target_module, name, original)


def _profile(
    key: str,
    *,
    tasks: bool = True,
    reminders: bool = True,
    habits: bool = True,
    reports: bool = True,
    integrations: bool = True,
) -> BotProfile:
    features = {name: False for name in DEFAULT_FEATURES}
    features.update(
        {
            "core": True,
            "tasks": tasks,
            "reminders": reminders and tasks,
            "habits": habits,
            "reports": reports,
            "integrations": integrations,
        }
    )
    return BotProfile(
        key=key,
        name=f"{key} bot",
        username=f"{key}_bot",
        token="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        features=features,
    )


class _FakeBot:
    def __init__(self) -> None:
        self.command_sets: list[list[str]] = []
        self.delete_calls = 0

    async def delete_my_commands(self) -> None:
        self.delete_calls += 1

    async def set_my_commands(self, commands) -> None:
        self.command_sets.append([command.command for command in commands])


class _FakeJobQueue:
    def __init__(self) -> None:
        self.jobs = []

    def get_jobs_by_name(self, name: str):
        return tuple(job for job in self.jobs if job.name == name)

    def _add(self, callback, *, name: str, **kwargs):
        job = SimpleNamespace(
            callback=callback,
            name=name,
            data=kwargs.get("data"),
            kwargs=kwargs,
        )
        self.jobs.append(job)
        return job

    def run_repeating(self, callback, *, name: str, **kwargs):
        return self._add(callback, name=name, **kwargs)

    def run_daily(self, callback, *, name: str, **kwargs):
        return self._add(callback, name=name, **kwargs)


class _FakeApp:
    def __init__(self, profile: BotProfile) -> None:
        self.bot_data = {"bot_config": profile}
        self.bot = _FakeBot()
        self.job_queue = _FakeJobQueue()


def _job_names(app: _FakeApp) -> list[str]:
    return [job.name for job in app.job_queue.jobs]


async def test_post_init_registers_expected_jobs_once_for_profile(monkeypatch, app_main):
    profile = _profile("alpha")
    app = _FakeApp(profile)
    init_db = AsyncMock()

    monkeypatch.setattr(app_main, "init_db", init_db)
    monkeypatch.setattr(app_main, "install_task_capabilities", lambda _app: None)

    await app_main.post_init(app)
    await app_main.post_init(app)

    expected = {
        "morning_today_tasks",
        "midday_summary_weekly",
        "habit_reminders",
        "weekly_habit_reports",
        "daily_admin_report",
        "jira_sync",
        "external_task_sync",
    }
    names = _job_names(app)

    assert set(names) == expected
    assert all(names.count(name) == 1 for name in expected)
    assert init_db.await_count == 2

    jobs = {job.name: job for job in app.job_queue.jobs}
    assert jobs["jira_sync"].data is profile
    assert jobs["external_task_sync"].data is profile


async def test_job_registration_and_callbacks_keep_bot_profiles_isolated(
    monkeypatch,
    app_main,
):
    alpha = _profile("alpha")
    beta = _profile("beta")
    alpha_app = _FakeApp(alpha)
    beta_app = _FakeApp(beta)

    monkeypatch.setattr(app_main, "init_db", AsyncMock())
    monkeypatch.setattr(app_main, "install_task_capabilities", lambda _app: None)

    await app_main.post_init(alpha_app)
    await app_main.post_init(beta_app)

    alpha_jobs = {job.name: job for job in alpha_app.job_queue.jobs}
    beta_jobs = {job.name: job for job in beta_app.job_queue.jobs}

    assert alpha_jobs["jira_sync"].data is alpha
    assert alpha_jobs["external_task_sync"].data is alpha
    assert beta_jobs["jira_sync"].data is beta
    assert beta_jobs["external_task_sync"].data is beta

    jira_sync = AsyncMock()
    external_sync = AsyncMock()
    monkeypatch.setattr(app_main, "run_jira_sync", jira_sync)
    monkeypatch.setattr(app_main, "run_external_sync", external_sync)

    alpha_context = SimpleNamespace(
        job=SimpleNamespace(data=alpha),
        application=SimpleNamespace(bot_data={"bot_config": beta}),
    )
    beta_context = SimpleNamespace(
        job=SimpleNamespace(data=beta),
        application=SimpleNamespace(bot_data={"bot_config": alpha}),
    )

    await app_main._jira_sync_job(alpha_context)
    await app_main._integration_sync_job(beta_context)

    jira_sync.assert_awaited_once_with(bot_key="alpha")
    external_sync.assert_awaited_once_with(bot_key="beta")


async def test_profile_without_integrations_does_not_register_sync_jobs(
    monkeypatch,
    app_main,
):
    profile = _profile("no-integrations", integrations=False)
    app = _FakeApp(profile)

    monkeypatch.setattr(app_main, "init_db", AsyncMock())
    monkeypatch.setattr(app_main, "install_task_capabilities", lambda _app: None)

    await app_main.post_init(app)

    assert "jira_sync" not in _job_names(app)
    assert "external_task_sync" not in _job_names(app)


def test_build_application_keeps_profile_context_and_handler_sets_isolated(
    monkeypatch,
    app_main,
):
    enabled = _profile("enabled", integrations=True)
    restricted = _profile(
        "restricted",
        tasks=False,
        reminders=False,
        habits=False,
        reports=False,
        integrations=False,
    )
    monkeypatch.setattr(app_main.task_handler, "_tag_flow_installed", True, raising=False)

    enabled_app = app_main.build_application(enabled)
    restricted_app = app_main.build_application(restricted)

    assert enabled_app.bot_data["bot_config"] is enabled
    assert restricted_app.bot_data["bot_config"] is restricted

    def commands(app):
        return {
            command
            for handlers in app.handlers.values()
            for handler in handlers
            if isinstance(handler, CommandHandler)
            for command in handler.commands
        }

    def conversations(app):
        return {
            handler.name
            for handlers in app.handlers.values()
            for handler in handlers
            if isinstance(handler, ConversationHandler)
        }

    enabled_commands = commands(enabled_app)
    restricted_commands = commands(restricted_app)

    assert {
        "start",
        "help",
        "add",
        "tasks",
        "jira_status",
        "jira_disconnect",
    } <= enabled_commands
    assert "jira_connection" in conversations(enabled_app)
    assert {"start", "help"} <= restricted_commands
    assert {
        "add",
        "tasks",
        "jira_status",
        "jira_disconnect",
    }.isdisjoint(restricted_commands)
    assert "jira_connection" not in conversations(restricted_app)


def test_main_wires_profiles_factory_and_shared_lifecycle_hooks(monkeypatch, app_main):
    profiles = [_profile("alpha"), _profile("beta")]
    called = {}

    async def fake_control_plane(factory, **kwargs):
        called["factory"] = factory
        called.update(kwargs)

    monkeypatch.setattr(app_main, "BOT_PROFILES", profiles)
    monkeypatch.setattr(app_main, "run_runtime_control_plane", fake_control_plane)

    app_main.main()

    assert called["factory"] is app_main.build_application
    assert called["initial_profiles"] is profiles
    assert called["startup_hook"] is app_main.start_integration_oauth_server
    assert called["shutdown_hook"] is app_main.stop_integration_oauth_server
