"""Central fine-grained permission registry for Bot Profiles."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    key: str
    label: str
    required_features: tuple[str, ...]


PERMISSION_REGISTRY: dict[str, PermissionDefinition] = {
    "core.use": PermissionDefinition("core.use", "Use Core", ("core",)),
    "tasks.view": PermissionDefinition("tasks.view", "View Tasks", ("tasks",)),
    "tasks.create": PermissionDefinition("tasks.create", "Create Tasks", ("tasks",)),
    "tasks.update": PermissionDefinition("tasks.update", "Edit Tasks", ("tasks",)),
    "tasks.status": PermissionDefinition("tasks.status", "Change Task Status", ("tasks",)),
    "teams.view": PermissionDefinition("teams.view", "View Teams", ("teams",)),
    "teams.manage": PermissionDefinition("teams.manage", "Manage Teams", ("teams",)),
    "assignment.manage": PermissionDefinition(
        "assignment.manage", "Manage Assignment", ("assignment", "teams", "tasks")
    ),
    "comments.manage": PermissionDefinition(
        "comments.manage", "Manage Comments", ("comments", "tasks")
    ),
    "attachments.manage": PermissionDefinition(
        "attachments.manage", "Manage Attachments", ("attachments", "tasks")
    ),
    "tags.manage": PermissionDefinition("tags.manage", "Manage Tags", ("tags", "tasks")),
    "categories.manage": PermissionDefinition(
        "categories.manage", "Manage Categories", ("categories", "tasks")
    ),
    "priority.set": PermissionDefinition(
        "priority.set", "Set Priority", ("priority", "tasks")
    ),
    "deadline.set": PermissionDefinition(
        "deadline.set", "Set Deadline", ("deadline", "tasks")
    ),
    "reminders.run": PermissionDefinition(
        "reminders.run", "Run Task Reminders", ("reminders", "tasks")
    ),
    "search.use": PermissionDefinition("search.use", "Use Search", ("search",)),
    "reports.view": PermissionDefinition("reports.view", "View Reports", ("reports",)),
    "ai.use": PermissionDefinition("ai.use", "Use AI", ("ai",)),
    "ai.tasks.create": PermissionDefinition(
        "ai.tasks.create", "Create Tasks with AI", ("ai", "tasks")
    ),
    "ai.habits.create": PermissionDefinition(
        "ai.habits.create", "Create Habits with AI", ("ai", "habits")
    ),
    "voice.use": PermissionDefinition("voice.use", "Use Voice", ("voice",)),
    "templates.use": PermissionDefinition(
        "templates.use", "Use Templates", ("templates",)
    ),
    "bulk_import.use": PermissionDefinition(
        "bulk_import.use", "Use Bulk Import", ("bulk_import",)
    ),
    "integrations.manage": PermissionDefinition(
        "integrations.manage", "Manage Integrations", ("integrations",)
    ),
    "integrations.sync": PermissionDefinition(
        "integrations.sync", "Run Integration Sync", ("integrations",)
    ),
    "guest_mode.use": PermissionDefinition(
        "guest_mode.use", "Use Guest Mode", ("guest_mode",)
    ),
    "contact.use": PermissionDefinition("contact.use", "Use Contact", ("contact",)),
    "donate.use": PermissionDefinition("donate.use", "Use Payments", ("donate",)),
    "custom_bots.manage": PermissionDefinition(
        "custom_bots.manage", "Manage Custom Bots", ("custom_bots",)
    ),
    "habits.view": PermissionDefinition("habits.view", "View Habits", ("habits",)),
    "habits.manage": PermissionDefinition(
        "habits.manage", "Manage Habits", ("habits",)
    ),
    "unassigned.view": PermissionDefinition(
        "unassigned.view", "View Unassigned Tasks", ("unassigned", "tasks")
    ),
}


def registry_payload() -> list[dict]:
    return [
        {
            "key": definition.key,
            "label": definition.label,
            "required_features": list(definition.required_features),
        }
        for definition in PERMISSION_REGISTRY.values()
    ]


def default_permission_policy(features) -> dict[str, bool]:
    enabled_features = {str(item).strip() for item in features or () if str(item).strip()}
    return {
        key: all(feature in enabled_features for feature in definition.required_features)
        for key, definition in PERMISSION_REGISTRY.items()
    }


def normalize_permission_policy(
    permissions,
    features,
    *,
    legacy_empty_defaults: bool = True,
) -> dict[str, bool]:
    defaults = default_permission_policy(features)

    if permissions is None:
        return defaults

    if isinstance(permissions, dict):
        if not permissions and legacy_empty_defaults:
            return defaults
        unknown = [str(key) for key in permissions if str(key) not in PERMISSION_REGISTRY]
        if unknown:
            raise ValueError("unknown_permission: " + ", ".join(sorted(unknown)))
        policy = {key: bool(permissions.get(key, False)) for key in PERMISSION_REGISTRY}
    else:
        selected = {str(item).strip() for item in permissions or () if str(item).strip()}
        unknown = sorted(selected - set(PERMISSION_REGISTRY))
        if unknown:
            raise ValueError("unknown_permission: " + ", ".join(unknown))
        policy = {key: key in selected for key in PERMISSION_REGISTRY}

    validate_permission_policy(policy, features)
    return policy


def validate_permission_policy(policy: dict[str, bool], features) -> None:
    enabled_features = {str(item).strip() for item in features or () if str(item).strip()}
    problems: list[str] = []
    for key, enabled in policy.items():
        if not enabled:
            continue
        definition = PERMISSION_REGISTRY.get(key)
        if definition is None:
            problems.append(f"unknown permission: {key}")
            continue
        missing = [
            feature
            for feature in definition.required_features
            if feature not in enabled_features
        ]
        if missing:
            problems.append(f"{key} requires features {', '.join(missing)}")
    if problems:
        raise ValueError("invalid_permission_dependencies: " + "; ".join(problems))


def permission_enabled(
    policy: dict[str, bool] | None,
    permission_key: str,
    features,
) -> bool:
    definition = PERMISSION_REGISTRY.get(permission_key)
    if definition is None:
        return False
    enabled_features = {str(item).strip() for item in features or () if str(item).strip()}
    if not all(feature in enabled_features for feature in definition.required_features):
        return False
    if not policy or permission_key not in policy:
        return True
    return bool(policy.get(permission_key))
