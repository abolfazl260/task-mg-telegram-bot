"""Canonical entry point for the manual task-creation flow.

The Rich Message installer patches ``handlers.task.add_task`` during
application setup. ``main.py`` imports this module before importing the
legacy ``add_task`` symbol, so initialize the same installer here as well.
That keeps the command registration and the menu entry on the exact same
canonical Rich Message flow, without duplicating the create-task state
machine.
"""

from handlers import task as task_handler
from handlers.tag_suggestions import install_tag_flow


# ``main.py`` imports ``start_create_task`` before its legacy
# ``from handlers.task import add_task`` import. Installing the flow here
# therefore makes that imported reference point at the Rich implementation.
# The normal application setup remains guarded by ``_tag_flow_installed``.
if not getattr(task_handler, "_tag_flow_installed", False):
    install_tag_flow(task_handler)


async def start_create_task(update, context):
    """Start the canonical Rich Message create-task flow."""
    return await task_handler.add_task(update, context)
