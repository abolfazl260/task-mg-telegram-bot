"""Process-wide OAuth callback listener for external integrations.

The callback endpoint is shared by all bot profiles. It must not be started or
stopped with an individual Telegram Application because bot hot-reload is
per-profile while the HTTP listener is process-wide.
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web

from services.integration_service import complete_oauth

logger = logging.getLogger(__name__)
_runner: web.AppRunner | None = None
_lock = asyncio.Lock()


async def _oauth_callback(request: web.Request) -> web.Response:
    provider = request.match_info.get("provider")
    error = request.query.get("error")
    if error:
        return web.Response(
            text=f"اتصال لغو شد: {error}",
            content_type="text/html",
            charset="utf-8",
        )

    code = request.query.get("code")
    state = request.query.get("state")
    if not code or not state:
        return web.Response(
            text="اطلاعات اتصال ناقص است.",
            status=400,
            content_type="text/html",
            charset="utf-8",
        )

    try:
        complete_oauth(provider, code, state)
    except Exception:
        logger.exception(
            "OAuth callback failed provider=%s operation=complete_oauth",
            provider,
        )
        return web.Response(
            text="<h2>اتصال ناموفق بود.</h2><p>جزئیات خطا ثبت شد. لطفاً دوباره تلاش کنید.</p>",
            status=500,
            content_type="text/html",
            charset="utf-8",
        )

    return web.Response(
        text="<h2>اتصال با موفقیت انجام شد.</h2><p>می‌توانید به تلگرام برگردید و همگام‌سازی را اجرا کنید.</p>",
        content_type="text/html",
        charset="utf-8",
    )


async def start_integration_oauth_server() -> None:
    global _runner
    base = os.getenv("INTEGRATION_REDIRECT_BASE_URL", "").strip()
    if not base:
        logger.info(
            "External task OAuth server disabled: "
            "INTEGRATION_REDIRECT_BASE_URL is not set"
        )
        return

    async with _lock:
        if _runner is not None:
            return

        oauth_app = web.Application()
        oauth_app.router.add_get(
            "/integrations/oauth/{provider}",
            _oauth_callback,
        )
        runner = web.AppRunner(oauth_app)
        await runner.setup()
        host = os.getenv("INTEGRATION_HOST", "0.0.0.0")
        port = int(os.getenv("INTEGRATION_PORT", "8080"))
        try:
            site = web.TCPSite(runner, host, port)
            await site.start()
        except Exception:
            await runner.cleanup()
            raise

        _runner = runner
        logger.info(
            "External task OAuth server started host=%s port=%s",
            host,
            port,
        )


async def stop_integration_oauth_server() -> None:
    global _runner
    async with _lock:
        runner = _runner
        _runner = None
    if runner is not None:
        await runner.cleanup()
        logger.info("External task OAuth server stopped")
