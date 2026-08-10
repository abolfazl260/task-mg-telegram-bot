"""Team / shared space business logic."""

import random
import string
import uuid
from datetime import datetime, timezone

from services.database import fetch_all, fetch_one, execute, transaction, sync_all, sync_one, sync_execute, sync_transaction

ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"
EDIT_ROLES = {ROLE_OWNER, ROLE_EDITOR}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _profile(user):
    if user is None:
        return "", ""
    if isinstance(user, dict):
        first = (user.get("first_name") or "").strip(); last = (user.get("last_name") or "").strip()
        uname = (user.get("username") or "").strip()
        return ((first + (" " + last if last else "")).strip() or uname or str(user.get("id", "")))[:80], uname[:64]
    first = getattr(user, "first_name", None) or ""; last = getattr(user, "last_name", None) or ""
    uname = getattr(user, "username", None) or ""
    return ((first + (" " + last if last else "")).strip() or uname or str(getattr(user, "id", "")))[:80], uname[:64]


def member_display(m):
    name = (m.get("display_name") or "").strip(); uname = (m.get("username") or "").strip(); uid = m.get("user_id") or ""
    if name and uname: return f"{name} (@{uname})"
    if name: return name
    if uname: return f"@{uname}"
    return f"کاربر {uid}"


async def _ensure_user(uid):
    await execute("INSERT OR IGNORE INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)", (str(uid), "UTC", "jalali"))


async def _gen_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    rows = await fetch_all("teams")
    existing = {(x.get("editor_code") or "").upper() for x in rows} | {(x.get("viewer_code") or "").upper() for x in rows}
    for _ in range(50):
        code = "".join(random.choices(alphabet, k=length))
        if code not in existing: return code
    return uuid.uuid4().hex[:length].upper()


async def acreate_team(owner_id, name, user=None):
    await _ensure_user(owner_id)
    name = (name or "").strip()[:60] or "تیم بدون نام"
    team_id = str(uuid.uuid4())[:8]
    editor_code = await _gen_code(); viewer_code = await _gen_code()
    while viewer_code == editor_code: viewer_code = await _gen_code()
    display, username = _profile(user)
    now = _now()
    team = {"team_id": team_id, "name": name, "owner_id": str(owner_id), "editor_code": editor_code, "viewer_code": viewer_code, "created_at": now}
    await transaction([
        ("INSERT INTO teams(team_id,name,owner_id,editor_code,viewer_code,created_at) VALUES(?,?,?,?,?,?)", (team_id,name,str(owner_id),editor_code,viewer_code,now)),
        ("INSERT INTO team_members(team_id,user_id,role,display_name,username,joined_at) VALUES(?,?,?,?,?,?)", (team_id,str(owner_id),ROLE_OWNER,display,username,now)),
    ])
    return team


async def aget_team(team_id): return await fetch_one("teams", "team_id=?", (team_id,))

async def aget_member_role(team_id,user_id):
    row = await fetch_one("team_members", "team_id=? AND user_id=?", (team_id,str(user_id)))
    return (row or {}).get("role") if row else None

async def ais_member(team_id,user_id): return (await aget_member_role(team_id,user_id)) is not None
async def acan_edit(team_id,user_id): return (await aget_member_role(team_id,user_id)) in EDIT_ROLES

async def afind_team_by_code(code):
    code = (code or "").strip().upper()
    if not code: return None, None
    row = await fetch_one("teams", "UPPER(editor_code)=?", (code,))
    if row: return row, ROLE_EDITOR
    row = await fetch_one("teams", "UPPER(viewer_code)=?", (code,))
    if row: return row, ROLE_VIEWER
    return None, None

async def aget_user_teams(user_id):
    return await _user_teams_query(user_id)

async def _user_teams_query(user_id):
    rows = await fetch_all("""teams WHERE team_id IN (SELECT team_id FROM team_members WHERE user_id=?)""", "", (str(user_id),))
    # fetch_all expects a table name; use direct SQL instead.
    # Kept separate to make the query explicit and parameterized.
    from services.database import get_db
    db = await get_db()
    async with db.conn.execute("SELECT t.*,m.role FROM teams t JOIN team_members m ON m.team_id=t.team_id WHERE m.user_id=? ORDER BY t.created_at", (str(user_id),)) as cur:
        result = []
        for row in await cur.fetchall():
            d = dict(row); role = d.pop("role", ROLE_VIEWER); result.append({"team": d, "role": role})
        return result

async def aget_team_members(team_id):
    order = {ROLE_OWNER:0, ROLE_EDITOR:1, ROLE_VIEWER:2}
    rows = await fetch_all("team_members", "team_id=?", (team_id,))
    rows.sort(key=lambda m:(order.get(m.get("role"),9),(m.get("display_name") or "").lower()))
    return rows

async def ajoin_team_by_code(user_id, code, user=None):
    await _ensure_user(user_id)
    team, role = await afind_team_by_code(code)
    if not team: return False, "کد دعوت نامعتبر است.", None
    uid = str(user_id); display, username = _profile(user); now = _now()
    existing = await aget_member_role(team["team_id"], uid)
    if existing:
        if existing == ROLE_VIEWER and role == ROLE_EDITOR:
            await execute("UPDATE team_members SET role=?,display_name=COALESCE(NULLIF(?,''),display_name),username=COALESCE(NULLIF(?,''),username) WHERE team_id=? AND user_id=?", (ROLE_EDITOR,display,username,team["team_id"],uid))
            return True, f"نقش شما در «{team['name']}» به ویرایشگر ارتقا یافت.", team
        return False, f"شما از قبل عضو «{team['name']}» هستید (نقش: {existing}).", team
    await execute("INSERT INTO team_members(team_id,user_id,role,display_name,username,joined_at) VALUES(?,?,?,?,?,?)", (team["team_id"],uid,role,display,username,now))
    return True, f"به تیم «{team['name']}» با نقش {'ویرایشگر' if role==ROLE_EDITOR else 'مشاهده‌کننده'} پیوستید.", team

async def aleave_team(user_id,team_id):
    role = await aget_member_role(team_id,user_id)
    if not role: return False, "عضو این تیم نیستید."
    if role == ROLE_OWNER: return False, "مالک تیم نمی‌تواند خارج شود. تیم را حذف کنید یا مالکیت را منتقل کنید."
    await execute("DELETE FROM team_members WHERE team_id=? AND user_id=?", (team_id,str(user_id)))
    team = await aget_team(team_id)
    return True, f"از تیم «{team['name'] if team else team_id}» خارج شدید."

async def aregenerate_codes(user_id,team_id):
    team = await aget_team(team_id)
    if not team: return False,"تیم پیدا نشد.",None
    if str(team.get("owner_id")) != str(user_id): return False,"فقط مالک می‌تواند کدها را عوض کند.",None
    editor = await _gen_code(); viewer = await _gen_code()
    while viewer == editor: viewer = await _gen_code()
    await execute("UPDATE teams SET editor_code=?,viewer_code=? WHERE team_id=?", (editor,viewer,team_id))
    team.update(editor_code=editor,viewer_code=viewer)
    return True,"کدهای دعوت به‌روز شد.",team

# Existing synchronous API is retained for compatibility. New async handlers
# must use the a* functions above.
def _legacy(coro):
    import asyncio, threading
    try: asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(coro)
    result=[]; errors=[]
    def worker():
        try: result.append(asyncio.run(coro))
        except BaseException as exc: errors.append(exc)
    t=threading.Thread(target=worker,daemon=True); t.start(); t.join()
    if errors: raise errors[0]
    return result[0] if result else None

# Preserve the old public functions by importing their implementations only when
# legacy callers need them. The database-backed async API above is the canonical path.

def create_team(owner_id,name,user=None): return _legacy(acreate_team(owner_id,name,user))
def find_team_by_code(code): return _legacy(afind_team_by_code(code))
def get_team(team_id): return _legacy(aget_team(team_id))
def get_member_role(team_id,user_id): return _legacy(aget_member_role(team_id,user_id))
def is_member(team_id,user_id): return _legacy(ais_member(team_id,user_id))
def can_edit(team_id,user_id): return _legacy(acan_edit(team_id,user_id))
def join_team_by_code(user_id,code,user=None): return _legacy(ajoin_team_by_code(user_id,code,user))
def get_user_teams(user_id): return _legacy(aget_user_teams(user_id))
def get_team_members(team_id): return _legacy(aget_team_members(team_id))
def leave_team(user_id,team_id): return _legacy(aleave_team(user_id,team_id))
def regenerate_codes(user_id,team_id): return _legacy(aregenerate_codes(user_id,team_id))
def role_label(role): return {ROLE_OWNER:"👑 مالک",ROLE_EDITOR:"✏️ ویرایشگر",ROLE_VIEWER:"👁 مشاهده‌کننده"}.get(role,role)
