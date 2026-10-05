import pytest

from services import database, team_service


@pytest.mark.asyncio
async def test_create_team_persists_owner_membership(test_db):
    team = await team_service.acreate_team(
        100,
        "Core Team",
        user={"id": 100, "first_name": "Owner", "username": "owner"},
    )

    stored = await team_service.aget_team(team["team_id"])
    members = await team_service.aget_team_members(team["team_id"])

    assert stored is not None
    assert stored["name"] == "Core Team"
    assert stored["owner_id"] == "100"
    assert [(m["user_id"], m["role"]) for m in members] == [
        ("100", team_service.ROLE_OWNER)
    ]


@pytest.mark.asyncio
async def test_editor_and_viewer_codes_assign_expected_roles(test_db):
    team = await team_service.acreate_team(100, "Join Roles")

    editor_ok, _, _ = await team_service.ajoin_team_by_code(
        200,
        team["editor_code"],
        user={"id": 200, "first_name": "Editor"},
    )
    viewer_ok, _, _ = await team_service.ajoin_team_by_code(
        300,
        team["viewer_code"],
        user={"id": 300, "first_name": "Viewer"},
    )

    assert editor_ok is True
    assert viewer_ok is True
    assert await team_service.aget_member_role(team["team_id"], 200) == team_service.ROLE_EDITOR
    assert await team_service.aget_member_role(team["team_id"], 300) == team_service.ROLE_VIEWER


@pytest.mark.asyncio
async def test_duplicate_join_does_not_create_duplicate_membership(test_db):
    team = await team_service.acreate_team(100, "No Duplicates")

    first_ok, _, _ = await team_service.ajoin_team_by_code(200, team["viewer_code"])
    second_ok, message, _ = await team_service.ajoin_team_by_code(200, team["viewer_code"])

    rows = await database.fetch_all(
        "team_members",
        "team_id=? AND user_id=?",
        (team["team_id"], "200"),
    )

    assert first_ok is True
    assert second_ok is False
    assert "از قبل عضو" in message
    assert len(rows) == 1
    assert rows[0]["role"] == team_service.ROLE_VIEWER


@pytest.mark.asyncio
async def test_existing_viewer_can_upgrade_to_editor_without_duplicate_row(test_db):
    team = await team_service.acreate_team(100, "Upgrade Role")
    await team_service.ajoin_team_by_code(200, team["viewer_code"])

    upgraded, message, _ = await team_service.ajoin_team_by_code(
        200, team["editor_code"]
    )

    rows = await database.fetch_all(
        "team_members",
        "team_id=? AND user_id=?",
        (team["team_id"], "200"),
    )
    assert upgraded is True
    assert "ارتقا" in message
    assert len(rows) == 1
    assert rows[0]["role"] == team_service.ROLE_EDITOR


@pytest.mark.asyncio
async def test_normal_member_can_leave_and_membership_is_removed(test_db):
    team = await team_service.acreate_team(100, "Leave Team")
    await team_service.ajoin_team_by_code(200, team["editor_code"])

    ok, message = await team_service.aleave_team(200, team["team_id"])

    assert ok is True
    assert "خارج شدید" in message
    assert await team_service.aget_member_role(team["team_id"], 200) is None


@pytest.mark.asyncio
async def test_owner_cannot_leave_team(test_db):
    team = await team_service.acreate_team(100, "Owner Locked")

    ok, message = await team_service.aleave_team(100, team["team_id"])

    assert ok is False
    assert "مالک تیم نمی‌تواند خارج شود" in message
    assert await team_service.aget_member_role(team["team_id"], 100) == team_service.ROLE_OWNER


@pytest.mark.asyncio
async def test_regenerated_codes_invalidate_old_codes_and_accept_new_codes(
    test_db, monkeypatch
):
    team = await team_service.acreate_team(100, "Rotate Codes")
    old_editor = team["editor_code"]
    old_viewer = team["viewer_code"]

    codes = iter(["NEWE22", "NEWV33"])

    async def fake_gen_code(length=6):
        return next(codes)

    monkeypatch.setattr(team_service, "_gen_code", fake_gen_code)

    ok, _, updated = await team_service.aregenerate_codes(100, team["team_id"])

    assert ok is True
    assert updated["editor_code"] == "NEWE22"
    assert updated["viewer_code"] == "NEWV33"

    assert await team_service.afind_team_by_code(old_editor) == (None, None)
    assert await team_service.afind_team_by_code(old_viewer) == (None, None)

    editor_team, editor_role = await team_service.afind_team_by_code("NEWE22")
    viewer_team, viewer_role = await team_service.afind_team_by_code("NEWV33")
    assert editor_team["team_id"] == team["team_id"]
    assert editor_role == team_service.ROLE_EDITOR
    assert viewer_team["team_id"] == team["team_id"]
    assert viewer_role == team_service.ROLE_VIEWER


@pytest.mark.asyncio
async def test_non_owner_cannot_regenerate_codes_and_unknown_codes_fail_safely(test_db):
    team = await team_service.acreate_team(100, "Owner Only")
    await team_service.ajoin_team_by_code(200, team["editor_code"])

    ok, message, result = await team_service.aregenerate_codes(200, team["team_id"])
    join_ok, join_message, joined_team = await team_service.ajoin_team_by_code(
        300, "NOT-A-REAL-CODE"
    )

    assert ok is False
    assert "فقط مالک" in message
    assert result is None

    assert join_ok is False
    assert "نامعتبر" in join_message
    assert joined_team is None
