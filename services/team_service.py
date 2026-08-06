"""Team / shared space business logic.

Roles:
  owner  — full control, sees invite codes
  editor — can create/edit team tasks
  viewer — read-only

Each team has two distinct invite codes (editor_code, viewer_code).
Users may belong to multiple teams.
"""

import random
import string
import uuid
from datetime import datetime

from services.team_manager import (
    init_teams,
    read_teams,
    append_team,
    write_teams,
    read_members,
    append_member,
    write_members,
)

ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

EDIT_ROLES = {ROLE_OWNER, ROLE_EDITOR}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _gen_code(length=6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # avoid ambiguous chars
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    existing = set()
    for t in read_teams():
        existing.add((t.get("editor_code") or "").upper())
        existing.add((t.get("viewer_code") or "").upper())
    for _ in range(50):
        code = "".join(random.choices(alphabet, k=length))
        if code not in existing:
            return code
    return uuid.uuid4().hex[:length].upper()


def create_team(owner_id, name: str) -> dict:
    """Create team; owner is added as owner role. Returns team dict."""

    init_teams()
    name = (name or "").strip()[:60] or "تیم بدون نام"
    team_id = str(uuid.uuid4())[:8]
    editor_code = _gen_code()
    viewer_code = _gen_code()
    while viewer_code == editor_code:
        viewer_code = _gen_code()

    team = {
        "team_id": team_id,
        "name": name,
        "owner_id": str(owner_id),
        "editor_code": editor_code,
        "viewer_code": viewer_code,
        "created_at": _now(),
    }
    append_team(team)
    append_member({
        "team_id": team_id,
        "user_id": str(owner_id),
        "role": ROLE_OWNER,
        "joined_at": _now(),
    })
    return team


def find_team_by_code(code: str):
    """Return (team, role) if code matches editor or viewer invite."""

    code = (code or "").strip().upper()
    if not code:
        return None, None
    for t in read_teams():
        if (t.get("editor_code") or "").upper() == code:
            return t, ROLE_EDITOR
        if (t.get("viewer_code") or "").upper() == code:
            return t, ROLE_VIEWER
    return None, None


def get_team(team_id: str):
    for t in read_teams():
        if t.get("team_id") == team_id:
            return t
    return None


def get_member_role(team_id: str, user_id) -> str | None:
    uid = str(user_id)
    for m in read_members():
        if m.get("team_id") == team_id and str(m.get("user_id")) == uid:
            return m.get("role") or ROLE_VIEWER
    return None


def is_member(team_id: str, user_id) -> bool:
    return get_member_role(team_id, user_id) is not None


def can_edit(team_id: str, user_id) -> bool:
    role = get_member_role(team_id, user_id)
    return role in EDIT_ROLES


def join_team_by_code(user_id, code: str) -> tuple:
    """
    Join team via invite code.
    Returns (ok, message, team_or_none).
    """

    init_teams()
    team, role = find_team_by_code(code)
    if not team:
        return False, "کد دعوت نامعتبر است.", None

    team_id = team["team_id"]
    uid = str(user_id)

    existing = get_member_role(team_id, uid)
    if existing:
        # already member — optionally upgrade viewer → editor if using editor code
        if existing == ROLE_VIEWER and role == ROLE_EDITOR:
            members = read_members()
            for m in members:
                if m.get("team_id") == team_id and str(m.get("user_id")) == uid:
                    m["role"] = ROLE_EDITOR
                    break
            write_members(members)
            return True, f"نقش شما در «{team['name']}» به ویرایشگر ارتقا یافت.", team
        return False, f"شما از قبل عضو «{team['name']}» هستید (نقش: {existing}).", team

    # owner cannot re-join as lower role via code on same team (already owner)
    append_member({
        "team_id": team_id,
        "user_id": uid,
        "role": role,
        "joined_at": _now(),
    })
    role_fa = "ویرایشگر" if role == ROLE_EDITOR else "مشاهده‌کننده"
    return True, f"به تیم «{team['name']}» با نقش {role_fa} پیوستید.", team


def get_user_teams(user_id) -> list:
    """List of {team, role} for user (multi-team)."""

    uid = str(user_id)
    members = [m for m in read_members() if str(m.get("user_id")) == uid]
    teams_by_id = {t["team_id"]: t for t in read_teams()}
    result = []
    for m in members:
        t = teams_by_id.get(m.get("team_id"))
        if t:
            result.append({"team": t, "role": m.get("role") or ROLE_VIEWER})
    return result


def get_team_members(team_id: str) -> list:
    return [m for m in read_members() if m.get("team_id") == team_id]


def leave_team(user_id, team_id: str) -> tuple:
    """Leave team. Owner cannot leave (must transfer/delete later)."""

    uid = str(user_id)
    role = get_member_role(team_id, uid)
    if not role:
        return False, "عضو این تیم نیستید."
    if role == ROLE_OWNER:
        return False, "مالک تیم نمی‌تواند خارج شود. تیم را حذف کنید یا مالکیت را منتقل کنید."

    members = [m for m in read_members() if not (m.get("team_id") == team_id and str(m.get("user_id")) == uid)]
    write_members(members)
    team = get_team(team_id)
    name = team["name"] if team else team_id
    return True, f"از تیم «{name}» خارج شدید."


def regenerate_codes(user_id, team_id: str) -> tuple:
    """Owner only: new editor + viewer codes."""

    team = get_team(team_id)
    if not team:
        return False, "تیم پیدا نشد.", None
    if str(team.get("owner_id")) != str(user_id):
        return False, "فقط مالک می‌تواند کدها را عوض کند.", None

    teams = read_teams()
    for t in teams:
        if t.get("team_id") == team_id:
            t["editor_code"] = _gen_code()
            t["viewer_code"] = _gen_code()
            while t["viewer_code"] == t["editor_code"]:
                t["viewer_code"] = _gen_code()
            write_teams(teams)
            return True, "کدهای دعوت به‌روز شد.", t
    return False, "خطا.", None


def role_label(role: str) -> str:
    return {
        ROLE_OWNER: "👑 مالک",
        ROLE_EDITOR: "✏️ ویرایشگر",
        ROLE_VIEWER: "👁 مشاهده‌کننده",
    }.get(role, role)
