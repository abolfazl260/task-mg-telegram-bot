"""Python 3.13 compatibility and Telegram command-menu ordering."""
import asyncio
from functools import wraps

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


# Telegram exposes commands in the order supplied to set_my_commands().
# Keep the requested primary commands at the top while preserving the
# existing order of every other command.
try:
    from telegram import Bot

    _original_set_my_commands = Bot.set_my_commands

    if not getattr(_original_set_my_commands, "_taskmg_ordered", False):
        _command_priority = {"ai": 0, "start": 1, "add": 2, "reports": 3}

        @wraps(_original_set_my_commands)
        async def _ordered_set_my_commands(self, commands, *args, **kwargs):
            commands = list(commands)
            indexed = list(enumerate(commands))
            indexed.sort(
                key=lambda item: (
                    _command_priority.get(item[1].command, 1000),
                    item[0],
                )
            )
            return await _original_set_my_commands(
                self,
                [command for _, command in indexed],
                *args,
                **kwargs,
            )

        _ordered_set_my_commands._taskmg_ordered = True
        Bot.set_my_commands = _ordered_set_my_commands
except Exception:
    # Never prevent the bot from starting if Telegram is unavailable during
    # interpreter initialization.
    pass
