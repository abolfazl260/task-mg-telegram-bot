from __future__ import annotations

from dataclasses import replace

import pytest

from bot_platform import BotProfile
from services import bot_runtime_manager
from services.bot_runtime_manager import BotRuntimeManager, profile_fingerprint


class FakeUpdater:
    def __init__(self) -> None:
        self.running = False
        self.polling_calls = 0
        self.stop_calls = 0

    async def start_polling(self, **_kwargs) -> None:
        self.running = True
        self.polling_calls += 1

    async def stop(self) -> None:
        self.running = False
        self.stop_calls += 1


class FakeApplication:
    def __init__(self, profile: BotProfile, *, fail_initialize: bool = False) -> None:
        self.profile = profile
        self.bot_data = {"bot_config": profile}
        self.updater = FakeUpdater()
        self.running = False
        self.initialized = False
        self.shutdown_calls = 0
        self.stop_calls = 0
        self.post_init = None
        self.fail_initialize = fail_initialize

    async def initialize(self) -> None:
        if self.fail_initialize:
            raise RuntimeError("telegram_invalid_token")
        self.initialized = True

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False
        self.stop_calls += 1

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


class FakeFactory:
    def __init__(self) -> None:
        self.created: list[FakeApplication] = []
        self.fail_tokens: set[str] = set()
        self.fail_initialize_tokens: set[str] = set()

    def __call__(self, profile: BotProfile) -> FakeApplication:
        if profile.token in self.fail_tokens:
            raise RuntimeError("factory_failed")
        app = FakeApplication(
            profile,
            fail_initialize=profile.token in self.fail_initialize_tokens,
        )
        self.created.append(app)
        return app


class StatusRecorder:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(
        self,
        bot_key: str,
        runtime_status: str,
        *,
        desired_status: str,
        event: str = "",
        error: str = "",
        clear_error: bool = False,
    ) -> None:
        self.events.append(
            {
                "bot_key": bot_key,
                "runtime_status": runtime_status,
                "desired_status": desired_status,
                "event": event,
                "error": error,
                "clear_error": clear_error,
            }
        )


def profile(
    key: str,
    token: str,
    *,
    features: dict[str, bool] | None = None,
    settings: dict | None = None,
) -> BotProfile:
    return BotProfile(
        key=key,
        name=key,
        username=f"{key}_bot",
        token=token,
        features=features or {"core": True, "tasks": True},
        settings=settings or {},
    )


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(
        bot_runtime_manager,
        "install_task_capabilities",
        lambda _app: None,
    )
    factory = FakeFactory()
    recorder = StatusRecorder()
    manager = BotRuntimeManager(
        factory,
        status_recorder=recorder,
        reconcile_seconds=1,
    )
    return manager, factory, recorder


@pytest.mark.asyncio
async def test_reconcile_starts_and_deactivates_only_target_bot(runtime):
    manager, factory, _recorder = runtime
    alpha = profile("alpha", "token-alpha")
    beta = profile("beta", "token-beta")

    await manager.reconcile([alpha, beta])

    alpha_app = manager.handles["alpha"].app
    beta_app = manager.handles["beta"].app
    assert alpha_app.running is True
    assert beta_app.running is True

    await manager.reconcile([beta])

    assert "alpha" not in manager.handles
    assert manager.handles["beta"].app is beta_app
    assert alpha_app.updater.stop_calls == 1
    assert alpha_app.stop_calls == 1
    assert alpha_app.shutdown_calls == 1
    assert beta_app.updater.stop_calls == 0
    assert len(factory.created) == 2


@pytest.mark.asyncio
async def test_token_change_reloads_only_changed_bot(runtime):
    manager, factory, recorder = runtime
    alpha = profile("alpha", "token-alpha-v1")
    beta = profile("beta", "token-beta")

    await manager.reconcile([alpha, beta])
    old_alpha_app = manager.handles["alpha"].app
    beta_app = manager.handles["beta"].app

    await manager.reconcile(
        [replace(alpha, token="token-alpha-v2"), beta]
    )

    new_alpha_app = manager.handles["alpha"].app
    assert new_alpha_app is not old_alpha_app
    assert new_alpha_app.profile.token == "token-alpha-v2"
    assert manager.handles["beta"].app is beta_app
    assert old_alpha_app.updater.stop_calls == 1
    assert beta_app.updater.stop_calls == 0
    assert len(factory.created) == 3
    assert any(
        event["bot_key"] == "alpha"
        and event["event"] == "reloaded"
        and event["runtime_status"] == "running"
        for event in recorder.events
    )


@pytest.mark.asyncio
async def test_feature_and_permission_changes_trigger_reload(runtime):
    manager, factory, _recorder = runtime
    alpha = profile(
        "alpha",
        "token-alpha",
        features={"core": True, "tasks": True},
        settings={"permissions": {"tasks.create": True}},
    )
    await manager.reconcile([alpha])
    first_app = manager.handles["alpha"].app

    feature_changed = replace(
        alpha,
        features={"core": True, "tasks": True, "reports": True},
    )
    await manager.reconcile([feature_changed])
    second_app = manager.handles["alpha"].app
    assert second_app is not first_app

    permission_changed = replace(
        feature_changed,
        settings={"permissions": {"tasks.create": False}},
    )
    await manager.reconcile([permission_changed])
    third_app = manager.handles["alpha"].app
    assert third_app is not second_app
    assert len(factory.created) == 3


@pytest.mark.asyncio
async def test_failed_new_bot_start_leaves_running_sibling_untouched(runtime):
    manager, factory, recorder = runtime
    alpha = profile("alpha", "token-alpha")
    broken = profile("broken", "token-broken")

    await manager.reconcile([alpha])
    alpha_app = manager.handles["alpha"].app
    factory.fail_tokens.add("token-broken")

    await manager.reconcile([alpha, broken])

    assert manager.handles["alpha"].app is alpha_app
    assert "broken" not in manager.handles
    assert alpha_app.updater.stop_calls == 0
    assert any(
        event["bot_key"] == "broken"
        and event["runtime_status"] == "error"
        and event["error"] == "start_failed:RuntimeError"
        for event in recorder.events
    )


@pytest.mark.asyncio
async def test_failed_reload_rolls_back_old_profile_and_keeps_sibling(runtime):
    manager, factory, recorder = runtime
    alpha = profile("alpha", "token-alpha-v1")
    beta = profile("beta", "token-beta")
    await manager.reconcile([alpha, beta])

    old_alpha_app = manager.handles["alpha"].app
    beta_app = manager.handles["beta"].app
    factory.fail_tokens.add("token-alpha-bad")

    await manager.reconcile(
        [replace(alpha, token="token-alpha-bad"), beta]
    )

    rollback_app = manager.handles["alpha"].app
    assert rollback_app is not old_alpha_app
    assert rollback_app.profile.token == "token-alpha-v1"
    assert manager.handles["beta"].app is beta_app
    assert beta_app.updater.stop_calls == 0
    assert any(
        event["bot_key"] == "alpha"
        and event["runtime_status"] == "running"
        and event["error"] == "reload_failed:RuntimeError"
        for event in recorder.events
    )


def test_profile_fingerprint_tracks_runtime_configuration_without_token_output():
    base = profile(
        "alpha",
        "secret-token",
        settings={"permissions": {"tasks.create": True}},
    )
    changed = replace(
        base,
        settings={"permissions": {"tasks.create": False}},
    )

    first = profile_fingerprint(base)
    second = profile_fingerprint(changed)

    assert first != second
    assert "secret-token" not in first
    assert len(first) == 64



@pytest.mark.asyncio
async def test_invalid_token_initialization_failure_is_isolated(runtime):
    manager, factory, recorder = runtime
    alpha = profile("alpha", "token-alpha")
    invalid = profile("invalid", "token-revoked")

    await manager.reconcile([alpha])
    alpha_app = manager.handles["alpha"].app
    factory.fail_initialize_tokens.add("token-revoked")

    await manager.reconcile([alpha, invalid])

    assert manager.handles["alpha"].app is alpha_app
    assert "invalid" not in manager.handles
    failed_app = next(
        app for app in factory.created if app.profile.key == "invalid"
    )
    assert failed_app.shutdown_calls == 1
    assert any(
        event["bot_key"] == "invalid"
        and event["runtime_status"] == "error"
        and event["error"] == "start_failed:RuntimeError"
        for event in recorder.events
    )
