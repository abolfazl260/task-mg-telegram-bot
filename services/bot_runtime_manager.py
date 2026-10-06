"""Dynamic per-bot Telegram Application lifecycle reconciler.

The reconciler treats each bot key as an independent runtime unit. Managed
configuration changes are applied without restarting sibling applications or
the process that hosts the Back Office.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from telegram import Update
from telegram.ext import Application

from services.bot_runtime_status import record_runtime_status
from services.task_capabilities import install_task_capabilities

if TYPE_CHECKING:
    from bot_platform import BotProfile

logger = logging.getLogger(__name__)

ApplicationFactory = Callable[["BotProfile"], Application]
ProfileLoader = Callable[[], list["BotProfile"]]
StatusRecorder = Callable[..., Awaitable[None]]


@dataclass
class RuntimeHandle:
    profile: "BotProfile"
    app: Application
    fingerprint: str


def profile_fingerprint(profile: "BotProfile") -> str:
    """Hash runtime-relevant configuration without logging or persisting secrets."""
    payload = asdict(profile)
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_error(action: str, exc: BaseException) -> str:
    return f"{action}:{type(exc).__name__}"


class BotRuntimeManager:
    def __init__(
        self,
        application_factory: ApplicationFactory,
        *,
        profile_loader: ProfileLoader | None = None,
        status_recorder: StatusRecorder = record_runtime_status,
        reconcile_seconds: float | None = None,
    ) -> None:
        self.application_factory = application_factory
        self.profile_loader = profile_loader or self._default_profile_loader
        self.status_recorder = status_recorder
        configured = os.getenv("BOT_RUNTIME_RECONCILE_SECONDS", "5").strip()
        self.reconcile_seconds = max(
            1.0,
            float(reconcile_seconds if reconcile_seconds is not None else configured or "5"),
        )
        self.handles: dict[str, RuntimeHandle] = {}
        self._reconcile_lock = asyncio.Lock()

    @staticmethod
    def _default_profile_loader() -> list["BotProfile"]:
        from bot_platform import load_bot_profiles

        return load_bot_profiles()

    async def _record(
        self,
        bot_key: str,
        runtime_status: str,
        *,
        desired_status: str,
        event: str = "",
        error: str = "",
    ) -> None:
        await self.status_recorder(
            bot_key,
            runtime_status,
            desired_status=desired_status,
            event=event,
            error=error,
        )

    async def _stop_app(self, app: Application) -> None:
        try:
            updater = getattr(app, "updater", None)
            if updater is not None and getattr(updater, "running", False):
                await updater.stop()
        finally:
            try:
                from bot_platform import _cleanup_application_resources

                await _cleanup_application_resources(app)
            finally:
                try:
                    if getattr(app, "running", False):
                        await app.stop()
                finally:
                    try:
                        await app.shutdown()
                    except RuntimeError:
                        # python-telegram-bot raises when shutdown is requested
                        # before initialization completed. Cleanup is already done.
                        pass

    async def _start_profile(self, profile: "BotProfile", *, event: str) -> RuntimeHandle:
        bot_key = profile.key
        await self._record(bot_key, "starting", desired_status="active")
        app: Application | None = None
        try:
            app = self.application_factory(profile)
            install_task_capabilities(app)
            await app.initialize()
            callback = getattr(app, "post_init", None)
            if callback is not None:
                await callback(app)
            await app.start()
            updater = getattr(app, "updater", None)
            if updater is not None:
                await updater.start_polling(
                    allowed_updates=[*Update.ALL_TYPES, "guest_message"]
                )
            handle = RuntimeHandle(
                profile=profile,
                app=app,
                fingerprint=profile_fingerprint(profile),
            )
            self.handles[bot_key] = handle
            await self._record(
                bot_key,
                "running",
                desired_status="active",
                event=event,
            )
            return handle
        except Exception as exc:
            if app is not None:
                try:
                    await self._stop_app(app)
                except Exception:
                    logger.exception("bot_runtime_failed_start_cleanup bot=%s", bot_key)
            await self._record(
                bot_key,
                "error",
                desired_status="active",
                error=_safe_error("start_failed", exc),
            )
            logger.exception("bot_runtime_start_failed bot=%s", bot_key)
            raise

    async def _stop_key(self, bot_key: str, *, desired_status: str) -> None:
        handle = self.handles.pop(bot_key, None)
        if handle is None:
            await self._record(
                bot_key,
                "stopped",
                desired_status=desired_status,
                event="stopped",
            )
            return
        await self._record(bot_key, "stopping", desired_status=desired_status)
        try:
            await self._stop_app(handle.app)
        except Exception as exc:
            await self._record(
                bot_key,
                "error",
                desired_status=desired_status,
                error=_safe_error("stop_failed", exc),
            )
            logger.exception("bot_runtime_stop_failed bot=%s", bot_key)
            return
        await self._record(
            bot_key,
            "stopped",
            desired_status=desired_status,
            event="stopped",
        )

    async def _reload_profile(self, profile: "BotProfile") -> None:
        bot_key = profile.key
        old = self.handles.get(bot_key)
        if old is None:
            await self._start_profile(profile, event="started")
            return

        await self._record(bot_key, "reloading", desired_status="active")
        self.handles.pop(bot_key, None)
        try:
            await self._stop_app(old.app)
        except Exception as exc:
            await self._record(
                bot_key,
                "error",
                desired_status="active",
                error=_safe_error("reload_stop_failed", exc),
            )
            logger.exception("bot_runtime_reload_stop_failed bot=%s", bot_key)
            return

        try:
            await self._start_profile(profile, event="reloaded")
            return
        except Exception as exc:
            reload_error = _safe_error("reload_failed", exc)

        # Best-effort rollback uses the previously running profile and creates a
        # fresh Application instance. Sibling bots are never touched.
        try:
            rollback = await self._start_profile(old.profile, event="started")
            self.handles[bot_key] = rollback
            await self._record(
                bot_key,
                "running",
                desired_status="active",
                error=reload_error,
            )
        except Exception:
            logger.exception("bot_runtime_rollback_failed bot=%s", bot_key)

    async def reconcile(self, profiles: list["BotProfile"] | None = None) -> None:
        async with self._reconcile_lock:
            if profiles is None:
                profiles = await asyncio.to_thread(self.profile_loader)
            desired = {profile.key: profile for profile in profiles if profile.active}

            for bot_key in list(self.handles):
                if bot_key not in desired:
                    await self._stop_key(bot_key, desired_status="inactive")

            for bot_key, profile in desired.items():
                handle = self.handles.get(bot_key)
                if handle is None:
                    try:
                        await self._start_profile(profile, event="started")
                    except Exception:
                        continue
                    continue
                if handle.fingerprint != profile_fingerprint(profile):
                    await self._reload_profile(profile)

    async def shutdown(self) -> None:
        for bot_key in list(self.handles):
            await self._stop_key(bot_key, desired_status="inactive")

    async def run(
        self,
        stop_event: asyncio.Event,
        *,
        initial_profiles: list["BotProfile"] | None = None,
    ) -> None:
        first = True
        while not stop_event.is_set():
            try:
                if first and initial_profiles is not None:
                    await self.reconcile(initial_profiles)
                else:
                    await self.reconcile()
            except Exception:
                # Loader/database failures must not terminate already running bots.
                logger.exception("bot_runtime_reconcile_failed")
            first = False
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.reconcile_seconds)
            except TimeoutError:
                pass


async def run_runtime_control_plane(
    application_factory: ApplicationFactory,
    *,
    initial_profiles: list["BotProfile"] | None = None,
    profile_loader: ProfileLoader | None = None,
    reconcile_seconds: float | None = None,
) -> None:
    """Run bot applications under a reconciler until SIGINT/SIGTERM."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed_signals: list[signal.Signals] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
            installed_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            pass

    from services.resource_monitor import monitor_resources
    from webapp.runtime import start_webapp_server

    start_webapp_server()
    resource_stop = asyncio.Event()
    resource_task = asyncio.create_task(
        monitor_resources(resource_stop),
        name="resource-monitor",
    )
    manager = BotRuntimeManager(
        application_factory,
        profile_loader=profile_loader,
        reconcile_seconds=reconcile_seconds,
    )
    try:
        await manager.run(stop_event, initial_profiles=initial_profiles)
    finally:
        await manager.shutdown()
        resource_stop.set()
        resource_task.cancel()
        try:
            await resource_task
        except asyncio.CancelledError:
            pass
        for sig in installed_signals:
            loop.remove_signal_handler(sig)
        try:
            from webapp.runtime import stop_webapp_server

            stop_webapp_server()
        except Exception:
            logger.exception("Failed to stop webapp server during shutdown")
        try:
            from services.database import close_all_dbs

            await close_all_dbs()
        except Exception:
            logger.exception("Failed to close database connections during shutdown")
        try:
            from services.database import shutdown_sync_loop

            shutdown_sync_loop()
        except Exception:
            logger.exception("Failed to close database compatibility loop during shutdown")
