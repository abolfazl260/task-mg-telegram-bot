from __future__ import annotations

import bot_platform


def test_load_bot_profiles_allows_managed_store_with_zero_active_bots(monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("BOT_PROFILES", "")
    monkeypatch.setenv("BOT_TOKEN", "")

    async def fake_seed():
        return []

    def fake_run(coro):
        coro.close()
        return []

    monkeypatch.setattr(bot_platform, "seed_default_profiles", fake_seed)
    monkeypatch.setattr(bot_platform, "_run", fake_run)
    monkeypatch.setattr(
        bot_platform,
        "read_custom_bots",
        lambda include_tokens=False: [
            {
                "bot_key": "clinic",
                "status": "inactive",
                "bot_token": "",
            }
        ],
    )
    monkeypatch.setattr(bot_platform, "_custom_bot_profiles", lambda: [])

    assert bot_platform.load_bot_profiles() == []
