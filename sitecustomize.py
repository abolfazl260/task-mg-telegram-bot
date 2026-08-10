"""Python 3.13 compatibility for older asyncio consumers.

python-telegram-bot versions that still call asyncio.get_event_loop() from
run_polling expect a current event loop to exist in the main thread. Python
3.13 no longer creates one automatically, so initialize it at interpreter
startup when none exists.
"""
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
