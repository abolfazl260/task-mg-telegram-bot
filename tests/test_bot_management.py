from __future__ import annotations

import pytest
import pytest_asyncio

from services import database
from services.bot_feature_registry import normalize_features
from services.bot_management_service import (
    create_managed_bot,
    get_managed_bot,
    list_managed_bots,
    seed_default_profiles,
    set_bot_status,
    update_managed_bot,
)


async def _valid_token(token: str) -> dict:
    if token.startswith("bad"):
        raise ValueError("invalid_token")
    return {"id": 123456, "username": "managed_test_bot"}


@pytest_asyncio.fixture(autouse=True)
async def isolated_db(tmp_path, monkeypatch):
    await database.close_all_dbs()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bot_management.db")
    await database.init_db()
    yield
    await database.close_all_dbs()


@pytest.mark.asyncio
async def test_seed_default_simple_and_clinic_profiles_is_idempotent():
    seeded = await seed_default_profiles()
    assert set(seeded) == {"simple", "clinic"}

    rows = {row["bot_key"]: row for row in await list_managed_bots()}
    assert rows["simple"]["status"] == "inactive"
    assert "tasks" in rows["simple"]["features"]
    assert "ai" not in rows["simple"]["features"]
    assert rows["clinic"]["profile_type"] == "clinic"
    assert "assignment" in rows["clinic"]["features"]
    assert "teams" in rows["clinic"]["features"]

    assert await seed_default_profiles() == []


@pytest.mark.asyncio
async def test_create_bot_rejects_duplicate_key_and_masks_token():
    payload = {
        "bot_key": "sales_bot",
        "display_name": "Sales Bot",
        "bot_token": "123456:abcdefghijklmnopqrstuvwxyzABCDE12345",
        "status": "inactive",
        "features": ["core", "tasks", "deadline"],
    }
    created = await create_managed_bot(payload, 42, token_validator=_valid_token)
    assert created["token_configured"] is True
    assert created["token_masked"].endswith("2345")
    assert "abcdefghijklmnopqrstuvwxyz" not in created["token_masked"]
    assert "bot_token" not in created

    with pytest.raises(ValueError, match="duplicate_bot_key"):
        await create_managed_bot(payload, 42, token_validator=_valid_token)


@pytest.mark.asyncio
async def test_create_bot_rejects_invalid_feature_dependency():
    with pytest.raises(ValueError, match="assignment requires teams"):
        await create_managed_bot(
            {
                "bot_key": "invalid_features",
                "display_name": "Invalid",
                "status": "inactive",
                "features": ["core", "tasks", "assignment"],
            },
            42,
            token_validator=_valid_token,
        )


@pytest.mark.asyncio
async def test_edit_replace_token_and_preserve_key():
    created = await create_managed_bot(
        {
            "bot_key": "ops_bot",
            "display_name": "Ops",
            "bot_token": "123456:abcdefghijklmnopqrstuvwxyzABCDE11111",
            "status": "inactive",
            "features": ["core", "tasks"],
        },
        1,
        token_validator=_valid_token,
    )
    assert created["display_name"] == "Ops"

    updated = await update_managed_bot(
        "ops_bot",
        {
            "display_name": "Operations",
            "bot_token": "123456:abcdefghijklmnopqrstuvwxyzABCDE22222",
            "features": ["core", "tasks", "teams", "assignment"],
        },
        1,
        token_validator=_valid_token,
    )
    assert updated["bot_key"] == "ops_bot"
    assert updated["display_name"] == "Operations"
    assert updated["token_masked"].endswith("2222")
    assert "assignment" in updated["features"]


@pytest.mark.asyncio
async def test_activate_deactivate_and_failure_isolation():
    token_a = "123456:abcdefghijklmnopqrstuvwxyzABCDE33333"
    token_b = "123456:abcdefghijklmnopqrstuvwxyzABCDE44444"
    await create_managed_bot(
        {"bot_key": "bot_a", "display_name": "A", "bot_token": token_a, "status": "inactive", "features": ["core", "tasks"]},
        1,
        token_validator=_valid_token,
    )
    await create_managed_bot(
        {"bot_key": "bot_b", "display_name": "B", "bot_token": token_b, "status": "inactive", "features": ["core", "tasks"]},
        1,
        token_validator=_valid_token,
    )

    activated = await set_bot_status("bot_a", True, 1, token_validator=_valid_token)
    assert activated["status"] == "active"
    assert (await get_managed_bot("bot_b"))["status"] == "inactive"

    async def fail_validator(token: str):
        raise ValueError("invalid_token")

    with pytest.raises(ValueError, match="invalid_token"):
        await set_bot_status("bot_b", True, 1, token_validator=fail_validator)

    assert (await get_managed_bot("bot_a"))["status"] == "active"
    assert (await get_managed_bot("bot_b"))["status"] == "inactive"

    deactivated = await set_bot_status("bot_a", False, 1, token_validator=_valid_token)
    assert deactivated["status"] == "inactive"


def test_feature_normalization_requires_core_and_dependencies():
    assert normalize_features(["tasks"]) == ["core", "tasks"]
    with pytest.raises(ValueError, match="assignment requires teams"):
        normalize_features(["core", "tasks", "assignment"])



@pytest.mark.asyncio
async def test_configured_clinic_json_is_migrated_to_managed_store(monkeypatch):
    monkeypatch.setenv("BOT_PROFILES", "clinic")
    monkeypatch.setenv("BOT_CLINIC_TOKEN", "123456:abcdefghijklmnopqrstuvwxyzABCDE55555")
    monkeypatch.setenv("BOT_CLINIC_USERNAME", "clinic_runtime_bot")

    seeded = await seed_default_profiles()
    assert "clinic" in seeded
    clinic = await get_managed_bot("clinic", include_token=True)
    assert clinic["status"] == "active"
    assert clinic["source"] == "migrated_json"
    assert clinic["bot_username"] == "clinic_runtime_bot"
    assert clinic["bot_token"].endswith("55555")

    public = await get_managed_bot("clinic")
    assert "bot_token" not in public
    assert public["token_masked"].endswith("5555")


def test_legacy_json_profile_preserves_task_option_feature_semantics(tmp_path, monkeypatch):
    from bot_platform import _load_json_profile

    profile_path = tmp_path / "legacy.json"
    profile_path.write_text(
        """{
          "key": "legacy",
          "name": "Legacy",
          "username": "legacy_bot",
          "features": {"tasks": true, "teams": true, "ai": false},
          "task_options": {
            "allow_assignment": false,
            "allow_tags": false,
            "allow_comments": true,
            "allow_categories": true
          }
        }""",
        encoding="utf-8",
    )
    monkeypatch.setenv("BOT_LEGACY_TOKEN", "test-token")
    profile = _load_json_profile(profile_path)
    assert profile.features["assignment"] is False
    assert profile.features["tags"] is False
    assert profile.features["comments"] is True
    assert profile.features["categories"] is True
    assert profile.features["voice"] is False
