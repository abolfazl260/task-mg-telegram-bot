"""Encrypt/rewrap managed Bot Profile tokens without printing secret values."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.bot_management_service import migrate_bot_token_storage
from services.database import close_all_dbs, init_db


async def _main() -> int:
    await init_db()
    try:
        result = await migrate_bot_token_storage(require_key=True)
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        await close_all_dbs()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
