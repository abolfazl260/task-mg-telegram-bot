"""Generic workspace authorization primitives owned by TaskMG Core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Mapping, Collection

from services.database import fetch_all_sql


class WorkspaceAccessError(PermissionError):
    """Generic resource-scope denial without leaking entity existence."""


@dataclass(frozen=True)
class WorkspaceScope:
    workspace_id: str
    actor_id: str

    ROLE_PERMISSIONS: ClassVar[Mapping[str, Collection[str]]] = {}
    CONTEXT_ROLES: ClassVar[frozenset[str]] = frozenset()
    ACCESS_ERROR: ClassVar[type[PermissionError]] = WorkspaceAccessError

    async def predicate(
        self,
        permission: str,
        alias: str = "e",
        *,
        context_predicate: str | None = None,
        unit_column: str = "unit_id",
    ):
        """Build a SQL predicate from persisted membership facts.

        The caller may supply a context predicate for roles that require
        entity-level constraints (for example, a clinician limited to their
        assigned references/cases). Role claims are always loaded from the DB.
        """
        if unit_column not in {"unit_id", "id"}:
            raise ValueError("invalid_scope_column")
        memberships = await fetch_all_sql(
            """SELECT m.*
               FROM workspace_memberships m
               JOIN workspaces w ON w.id=m.workspace_id
               WHERE m.workspace_id=? AND m.user_id=?
                 AND m.status='active' AND w.status='active'""",
            (self.workspace_id, str(self.actor_id)),
        )
        terms: list[str] = []
        params: list[str] = [self.workspace_id]
        for member in memberships:
            if permission not in self.ROLE_PERMISSIONS.get(member["role"], ()):
                continue
            term = "1=1"
            if member["unit_id"]:
                term = f"{alias}.{unit_column}=?"
                params.append(member["unit_id"])
            if member["role"] in self.CONTEXT_ROLES:
                if not context_predicate:
                    continue
                term += f" AND ({context_predicate})"
                params.extend([str(self.actor_id), str(self.actor_id)])
            terms.append(f"({term})")
        if not terms:
            raise self.ACCESS_ERROR("forbidden")
        return f"{alias}.workspace_id=? AND ({' OR '.join(terms)})", tuple(params)

    async def unit(
        self,
        unit_id: str,
        permission: str,
        *,
        context_predicate: str | None = "?=?",
    ):
        pred, args = await self.predicate(
            permission,
            "u",
            context_predicate=context_predicate,
            unit_column="id",
        )
        rows = await fetch_all_sql(
            f"SELECT u.* FROM workspace_units u "
            f"WHERE {pred} AND u.id=? AND u.status='active'",  # nosec B608
            args + (unit_id,),
        )
        if not rows:
            raise self.ACCESS_ERROR("forbidden")
        return rows[0]


async def actor_workspaces(actor_id: str, bot_key: str):
    return await fetch_all_sql(
        """SELECT DISTINCT
               w.id AS workspace_id,
               w.name,
               w.workspace_type,
               m.unit_id,
               m.role
           FROM workspaces w
           JOIN workspace_memberships m ON m.workspace_id=w.id
           WHERE w.bot_key=? AND w.status='active'
             AND m.user_id=? AND m.status='active'""",
        (bot_key, str(actor_id)),
    )
