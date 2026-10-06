from __future__ import annotations

import pytest

from bot_platform import BotProfile
from services.bot_permission_registry import (
    default_permission_policy,
    normalize_permission_policy,
    permission_enabled,
)


def test_default_permissions_follow_enabled_features():
    policy = default_permission_policy(["core", "tasks", "priority"])

    assert policy["core.use"] is True
    assert policy["tasks.view"] is True
    assert policy["tasks.create"] is True
    assert policy["priority.set"] is True
    assert policy["reports.view"] is False
    assert policy["assignment.manage"] is False


def test_permission_policy_rejects_permission_for_disabled_feature():
    with pytest.raises(ValueError, match="invalid_permission_dependencies"):
        normalize_permission_policy(
            {"reports.view": True},
            ["core", "tasks"],
            legacy_empty_defaults=False,
        )


def test_legacy_empty_permission_policy_defaults_to_existing_behavior():
    policy = normalize_permission_policy({}, ["core", "tasks", "deadline"])

    assert policy["tasks.view"] is True
    assert policy["tasks.create"] is True
    assert policy["deadline.set"] is True
    assert policy["reports.view"] is False


def test_explicit_all_false_policy_is_supported():
    policy = normalize_permission_policy([], ["core", "tasks"])

    assert policy["core.use"] is False
    assert policy["tasks.view"] is False
    assert policy["tasks.create"] is False


def test_permission_enabled_requires_feature_and_policy():
    features = ["core", "tasks", "priority"]
    assert permission_enabled({}, "priority.set", features) is True
    assert permission_enabled({"priority.set": False}, "priority.set", features) is False
    assert permission_enabled({"reports.view": True}, "reports.view", features) is False


def test_bot_profile_runtime_permission_check_uses_central_policy():
    profile = BotProfile(
        key="restricted",
        name="Restricted",
        username="restricted_bot",
        token="token",
        features={"core": True, "tasks": True, "reports": True},
        permissions={"tasks.view": True, "tasks.create": False, "reports.view": True},
    )

    assert profile.permission_enabled("tasks.view") is True
    assert profile.permission_enabled("tasks.create") is False
    assert profile.permission_enabled("reports.view") is True
    assert profile.permission_enabled("priority.set") is False
