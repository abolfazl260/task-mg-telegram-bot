"""Reusable operational-domain primitives for TaskMG Core.

Verticals such as Healthcare configure terminology and role policy on top of
these workspace/reference/case/workflow/follow-up capabilities.
"""

from services.operations.access import WorkspaceAccessError, WorkspaceScope

__all__ = ["WorkspaceAccessError", "WorkspaceScope"]
