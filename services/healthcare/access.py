"""Healthcare role policy layered on generic TaskMG workspace access."""

from __future__ import annotations

from dataclasses import dataclass

from services.operations.access import (
    WorkspaceAccessError,
    WorkspaceScope,
    actor_workspaces,
)


class ClinicAccessError(WorkspaceAccessError):
    """Healthcare-safe denial that intentionally hides entity existence."""


VIEW = frozenset({"patients.view", "cases.view", "tasks.view", "followups.view"})
WORK = VIEW | {"patients.manage", "cases.manage", "tasks.manage", "followups.manage"}
ROLE_PERMISSIONS = {
    "owner": WORK
    | {
        "branches.manage",
        "memberships.manage",
        "reports.view",
        "exports.create",
        "workflows.manage",
        "audit.view",
        "integrations.manage",
    },
    "admin": WORK
    | {
        "branches.manage",
        "memberships.manage",
        "reports.view",
        "exports.create",
        "workflows.manage",
        "audit.view",
        "integrations.manage",
    },
    "manager": WORK
    | {"reports.view", "exports.create", "workflows.manage", "audit.view"},
    "doctor": VIEW | {"cases.manage", "tasks.manage", "followups.manage"},
    "dentist": VIEW | {"cases.manage", "tasks.manage", "followups.manage"},
    "reception": WORK,
    "coordinator": WORK,
    "assistant": VIEW | {"tasks.manage", "followups.manage"},
}


@dataclass(frozen=True)
class Scope(WorkspaceScope):
    ROLE_PERMISSIONS = ROLE_PERMISSIONS
    CONTEXT_ROLES = frozenset({"doctor", "dentist"})
    ACCESS_ERROR = ClinicAccessError

    @property
    def organization_id(self) -> str:
        """Healthcare terminology alias retained at the channel boundary."""
        return self.workspace_id

    async def predicate(
        self,
        permission: str,
        alias: str = "e",
        *,
        doctor_context: str | None = None,
        branch_column: str = "unit_id",
    ):
        unit_column = "unit_id" if branch_column == "branch_id" else branch_column
        return await super().predicate(
            permission,
            alias,
            context_predicate=doctor_context,
            unit_column=unit_column,
        )

    async def branch(self, branch_id: str, permission: str):
        return await self.unit(
            branch_id,
            permission,
            context_predicate="?=?",
        )


async def actor_scopes(actor_id: str, bot_key: str):
    """Return Healthcare terminology without changing the Core persistence model."""
    rows = await actor_workspaces(actor_id, bot_key)
    return [
        {
            "organization_id": row["workspace_id"],
            "name": row["name"],
            "branch_id": row["unit_id"],
            "role": row["role"],
        }
        for row in rows
    ]
