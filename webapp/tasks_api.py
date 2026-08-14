"""Task access helpers for the Telegram Web App."""
from __future__ import annotations

from services import task_service
from webapp.bot_profile import set_webapp_bot_context

class WebAppTaskAccessError(PermissionError):
    """The authenticated user cannot access or modify the task."""

def _set_context(bot_key: str) -> str:
    return set_webapp_bot_context(bot_key)

async def list_tasks(user_id: int, bot_key: str, *, team_id: str | None = None, active_only: bool = False):
    _set_context(bot_key)
    return await (task_service.get_active_tasks_async(user_id, team_id) if active_only else task_service.get_all_user_tasks_async(user_id, team_id))

async def get_task(user_id: int, task_id: str, bot_key: str):
    _set_context(bot_key)
    task = await task_service.get_task_by_id_async(task_id)
    if not task: return None
    if not any(str(item.get("id")) == str(task_id) for item in await task_service.get_all_user_tasks_async(user_id)):
        raise WebAppTaskAccessError("Task is not visible to this user")
    return task

async def create_task(user_id: int, bot_key: str, *, title: str, priority: str = "medium", deadline: str = "", category: str = "", tags: str = "", description: str = "", team_id: str = ""):
    _set_context(bot_key)
    return await task_service.create_task_async(user_id=user_id,title=title,priority=priority,deadline=deadline,category=category,tags=tags,description=description,team_id=team_id)

async def update_task(user_id: int, task_id: str, bot_key: str, **changes):
    _set_context(bot_key)
    return await task_service.update_task_async(task_id, user_id, **changes)

async def change_status(user_id: int, task_id: str, new_status: str, bot_key: str) -> bool:
    _set_context(bot_key)
    task = await task_service.get_task_by_id_async(task_id)
    if not task or not await task_service.user_can_modify_task_async(user_id, task):
        raise WebAppTaskAccessError("Task cannot be modified by this user")
    return await task_service.change_task_status_async(task_id, new_status)
