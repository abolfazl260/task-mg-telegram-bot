"""Central bot capability registry and default profile templates.

This is the single code-level registry used by Back Office and runtime profile
validation. UI code must consume this registry through the admin API instead of
duplicating feature names or dependency rules.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDefinition:
    key: str
    label: str
    dependencies: tuple[str, ...] = ()
    runtime_supported: bool = True


FEATURE_REGISTRY: dict[str, FeatureDefinition] = {
    "core": FeatureDefinition("core", "Core"),
    "tasks": FeatureDefinition("tasks", "Tasks", ("core",)),
    "teams": FeatureDefinition("teams", "Teams", ("core",)),
    "assignment": FeatureDefinition("assignment", "Assignment", ("tasks",)),
    "comments": FeatureDefinition("comments", "Comments", ("tasks",)),
    "attachments": FeatureDefinition("attachments", "Attachments", ("tasks",)),
    "tags": FeatureDefinition("tags", "Tags", ("tasks",)),
    "categories": FeatureDefinition("categories", "Categories", ("tasks",)),
    "priority": FeatureDefinition("priority", "Priority", ("tasks",)),
    "deadline": FeatureDefinition("deadline", "Deadline", ("tasks",)),
    "reminders": FeatureDefinition("reminders", "Reminders", ("tasks",)),
    "search": FeatureDefinition("search", "Search", ("core",)),
    "reports": FeatureDefinition("reports", "Reports", ("core",)),
    "healthcare": FeatureDefinition("healthcare", "Healthcare Operations", ("core",)),
    "clinic_staff_reminders": FeatureDefinition("clinic_staff_reminders", "Clinic Staff Reminders", ("healthcare",)),
    "ai": FeatureDefinition("ai", "AI", ("core",)),
    "voice": FeatureDefinition("voice", "Voice", ("core", "ai")),
    "templates": FeatureDefinition("templates", "Templates", ("core",)),
    "bulk_import": FeatureDefinition("bulk_import", "Bulk Import", ("core",)),
    "integrations": FeatureDefinition("integrations", "Integrations", ("core",)),
    "jira": FeatureDefinition("jira", "Jira", ("integrations",)),
    "google_tasks": FeatureDefinition("google_tasks", "Google Tasks", ("integrations",)),
    "guest_mode": FeatureDefinition("guest_mode", "Guest Mode", ("core",)),
    "contact": FeatureDefinition("contact", "Contact", ("core",)),
    "donate": FeatureDefinition("donate", "Donate / Payments", ("core",)),
    "custom_bots": FeatureDefinition("custom_bots", "Custom Bots", ("core",)),
    "habits": FeatureDefinition("habits", "Habits", ("core",)),
    "unassigned": FeatureDefinition("unassigned", "Unassigned Tasks", ("tasks",)),
}

# Minimal profile intentionally excludes teams, AI, integrations and vertical flows.
SIMPLE_FEATURES = ("core", "tasks", "deadline", "priority", "contact")
CLINIC_FEATURES = (
    "core", "tasks", "teams", "assignment", "comments", "attachments",
    "tags", "categories", "priority", "deadline", "reminders", "search",
    "reports", "contact", "unassigned", "healthcare", "clinic_staff_reminders",
)

DEFAULT_PROFILE_TEMPLATES = {
    "simple": {
        "name": "TaskMG Simple",
        "description": "Minimal TaskMG profile for basic task management.",
        "features": SIMPLE_FEATURES,
    },
    "clinic": {
        "name": "TaskMG Clinic",
        "description": "Healthcare/clinic operational profile built on reusable Core capabilities.",
        "features": CLINIC_FEATURES,
    },
}


def registry_payload() -> list[dict]:
    return [
        {
            "key": feature.key,
            "label": feature.label,
            "dependencies": list(feature.dependencies),
            "runtime_supported": feature.runtime_supported,
        }
        for feature in FEATURE_REGISTRY.values()
    ]


def normalize_features(features) -> list[str]:
    selected: list[str] = []
    for raw in features or ():
        key = str(raw).strip()
        if key and key in FEATURE_REGISTRY and key not in selected:
            selected.append(key)
    if not selected:
        selected = ["core", "tasks"]
    if "core" not in selected:
        selected.insert(0, "core")
    validate_feature_dependencies(selected)
    return selected


def validate_feature_dependencies(features) -> None:
    selected = set(features)
    problems: list[str] = []
    for key in selected:
        definition = FEATURE_REGISTRY.get(key)
        if definition is None:
            problems.append(f"unknown feature: {key}")
            continue
        missing = [dependency for dependency in definition.dependencies if dependency not in selected]
        if missing:
            problems.append(f"{key} requires {', '.join(missing)}")
    if "assignment" in selected and "teams" not in selected:
        # Assignment can exist for personal tasks, but current TaskMG assignment
        # flow is team-based; keep the managed profile configuration conservative.
        problems.append("assignment requires teams in the current runtime")
    if problems:
        raise ValueError("invalid_feature_dependencies: " + "; ".join(problems))
