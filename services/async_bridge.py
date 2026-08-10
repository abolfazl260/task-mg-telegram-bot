"""Async bridge for legacy service APIs.

Handlers should use these proxies while the service layer is being fully
migrated to native aiosqlite. Calls execute off the Telegram event loop,
so synchronous legacy code cannot block update processing.
"""

from __future__ import annotations

import asyncio
from functools import partial
from importlib import import_module


class AsyncServiceProxy:
    def __init__(self, module_name: str):
        self._module_name = module_name

    async def call(self, method: str, *args, **kwargs):
        module = import_module(self._module_name)
        fn = getattr(module, method)
        return await asyncio.to_thread(partial(fn, *args, **kwargs))

    def __getattr__(self, method: str):
        async def runner(*args, **kwargs):
            return await self.call(method, *args, **kwargs)
        runner.__name__ = method
        return runner


task = AsyncServiceProxy("services.task_service")
user = AsyncServiceProxy("services.user_service")
habit = AsyncServiceProxy("services.habit_service")
team = AsyncServiceProxy("services.team_service")
integration = AsyncServiceProxy("services.integration_service")
jira = AsyncServiceProxy("services.jira_service")
custom_bot = AsyncServiceProxy("services.custom_bot_service")
business = AsyncServiceProxy("services.business_service")
