"""Application logging configuration.

Creates two persistent rotating log files:
- logs/errors.log: WARNING and ERROR/CRITICAL records only.
- logs/app.log: every application log record (DEBUG and above).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent / "logs"
ALL_LOG_PATH = LOG_DIR / "app.log"
ERROR_LOG_PATH = LOG_DIR / "errors.log"

_MAX_BYTES = 20 * 1024 * 1024
_BACKUP_COUNT = 10
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S,%(msecs)03d"


def setup_logging() -> None:
    """Configure console + persistent all/error log streams exactly once."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    if not any(getattr(handler, "_task_mg_all_log", False) for handler in root.handlers):
        all_handler = RotatingFileHandler(
            ALL_LOG_PATH,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
            delay=True,
        )
        all_handler.setLevel(logging.DEBUG)
        all_handler.setFormatter(formatter)
        all_handler._task_mg_all_log = True
        root.addHandler(all_handler)

    if not any(getattr(handler, "_task_mg_error_log", False) for handler in root.handlers):
        error_handler = RotatingFileHandler(
            ERROR_LOG_PATH,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
            delay=True,
        )
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(formatter)
        error_handler._task_mg_error_log = True
        root.addHandler(error_handler)

    # Keep terminal output useful while preserving the existing INFO behavior.
    if not any(getattr(handler, "_task_mg_console", False) for handler in root.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        console_handler._task_mg_console = True
        root.addHandler(console_handler)

    # Third-party HTTP logs are already noisy in production.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


__all__ = ["setup_logging", "LOG_DIR", "ALL_LOG_PATH", "ERROR_LOG_PATH"]
