"""Canonical entry point for the manual task-creation flow.

The rich create-task installer replaces ``handlers.task.add_task`` with the
Rich Message implementation during application setup. This module provides a
stable entry point for both command and menu-based creation without duplicating
or reimplementing the flow.
"""

from handlers import task as task_handler


async def start_create_task(update, context):
    """Start the canonical Rich Message create-task flow."""
    return await task_handler.add_task(update, context)
