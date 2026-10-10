"""Task access helpers for the Telegram Web App."""
from __future__ import annotations

from services import task_service
from services.work_item_type_service import list_work_item_types_async
from webapp.bot_profile import set_webapp_bot_context

class WebAppTaskAccessError(PermissionError):
    """The authenticated user cannot access or modify the task."""

def _set_context(bot_key: str) -> str:
    try:
        return set_webapp_bot_context(bot_key)
    except TypeError:
        # Keep compatibility with tests/legacy providers exposing the original
        # zero-argument context setter.
        return set_webapp_bot_context()

async def list_tasks(user_id: int, bot_key: str = "default", *, team_id: str | None = None, active_only: bool = False, work_item_type: str | None = None):
    _set_context(bot_key)
    getter = task_service.get_active_tasks_async if active_only else task_service.get_all_user_tasks_async
    if work_item_type:
        return await getter(user_id, team_id, work_item_type=work_item_type)
    return await getter(user_id, team_id)

def task_page_params(query: dict) -> tuple[int, int]:
    """Validate bounded list parameters supplied by either Web App adapter."""
    try:
        limit = int((query.get("limit") or [str(task_service.DEFAULT_TASK_PAGE_SIZE)])[0])
        offset = int((query.get("offset") or ["0"])[0])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_pagination") from exc
    if not 1 <= limit <= task_service.MAX_TASK_PAGE_SIZE or offset < 0:
        raise ValueError("invalid_pagination")
    return limit, offset


async def list_tasks_page(
    user_id: int, bot_key: str = "default", *, team_id: str | None = None,
    active_only: bool = False, work_item_type: str | None = None,
    limit: int = task_service.DEFAULT_TASK_PAGE_SIZE, offset: int = 0,
) -> dict:
    _set_context(bot_key)
    return await task_service.list_visible_tasks_page_async(
        user_id, team_id, active=active_only, work_item_type=work_item_type,
        limit=limit, offset=offset,
    )


async def list_work_item_types(bot_key: str = "default"):
    _set_context(bot_key)
    return await list_work_item_types_async(bot_key)

async def get_task(user_id: int, task_id: str, bot_key: str = "default"):
    _set_context(bot_key)
    task = await task_service.get_task_by_id_async(task_id)
    if not task:
        return None
    visible = await task_service.get_visible_task_by_id_async(user_id, task_id)
    if visible is None:
        raise WebAppTaskAccessError("Task is not visible to this user")
    return visible

async def create_task(user_id: int, bot_key: str = "default", *, title: str, priority: str = "medium", deadline: str = "", category: str = "", tags: str = "", description: str = "", team_id: str = "", work_item_type: str | None = None):
    _set_context(bot_key)
    return await task_service.create_task_async(user_id=user_id,title=title,priority=priority,deadline=deadline,category=category,tags=tags,description=description,team_id=team_id,work_item_type=work_item_type)

async def update_task(user_id: int, task_id: str, bot_key: str = "default", **changes):
    _set_context(bot_key)
    return await task_service.update_task_async(task_id, user_id, **changes)

async def change_status(user_id: int, task_id: str, new_status: str, bot_key: str = "default") -> bool:
    _set_context(bot_key)
    task = await task_service.get_task_by_id_async(task_id)
    if not task or not await task_service.user_can_modify_task_async(user_id, task):
        raise WebAppTaskAccessError("Task cannot be modified by this user")
    return await task_service.change_task_status_async(task_id, new_status, user_id)
