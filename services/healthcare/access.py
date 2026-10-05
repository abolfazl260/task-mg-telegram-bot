"""Shared clinic authorization for Telegram, Web and domain operations."""

from __future__ import annotations

from dataclasses import dataclass

from services.database import fetch_all_sql


class ClinicAccessError(PermissionError):
    """Intentionally generic to avoid leaking patient/entity existence."""


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
class Scope:
    organization_id: str
    actor_id: str

    async def predicate(
        self,
        permission: str,
        alias: str = "e",
        *,
        doctor_context: str | None = None,
        branch_column="branch_id",
    ):
        """Return a DB predicate, never an in-memory filter or client role claim."""
        if branch_column not in {"branch_id", "id"}:
            raise ValueError("invalid_scope_column")
        memberships = await fetch_all_sql(
            """SELECT m.* FROM clinic_memberships m JOIN clinic_organizations o ON o.id=m.organization_id
               WHERE m.organization_id=? AND m.user_id=? AND m.status='active' AND o.status='active'""",
            (self.organization_id, str(self.actor_id)),
        )
        terms, params = [], [self.organization_id]
        for member in memberships:
            if permission not in ROLE_PERMISSIONS.get(member["role"], ()):
                continue
            term = "1=1"
            if member["branch_id"]:
                term = f"{alias}.{branch_column}=?"
                params.append(member["branch_id"])
            if member["role"] in {"doctor", "dentist"}:
                if not doctor_context:
                    continue
                term += f" AND ({doctor_context})"
                params.extend([str(self.actor_id), str(self.actor_id)])
            terms.append(f"({term})")
        if not terms:
            raise ClinicAccessError("forbidden")
        return f"{alias}.organization_id=? AND ({' OR '.join(terms)})", tuple(params)

    async def branch(self, branch_id: str, permission: str):
        # Doctor scope on creation is limited to their own doctor context by the
        # service; branch checking alone grants no entity access.
        pred, args = await self.predicate(
            permission, "b", doctor_context="?=?", branch_column="id"
        )
        row = await fetch_all_sql(
            f"SELECT b.* FROM clinic_branches b WHERE {pred} AND b.id=? AND b.status='active'",  # nosec B608
            args + (branch_id,),
        )
        if not row:
            raise ClinicAccessError("forbidden")
        return row[0]


async def actor_scopes(actor_id: str, bot_key: str):
    return await fetch_all_sql(
        """SELECT DISTINCT o.id AS organization_id,o.name,m.branch_id,m.role FROM clinic_organizations o
           JOIN clinic_memberships m ON m.organization_id=o.id
           WHERE o.bot_key=? AND o.status='active' AND m.user_id=? AND m.status='active'""",
        (bot_key, str(actor_id)),
    )
