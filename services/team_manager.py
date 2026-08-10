from services.database import sync_all, sync_one, sync_execute, sync_transaction


def init_teams():
    from services.user_service import init_users
    init_users()


def read_teams():
    return sync_all("teams")


def write_teams(rows):
    """Replace the mutable team fields atomically without touching other rows."""
    statements = []
    for r in rows:
        statements.append(
            (
                "UPDATE teams SET name=?,owner_id=?,editor_code=?,viewer_code=?,created_at=? WHERE team_id=?",
                (
                    r.get("name", ""),
                    str(r.get("owner_id", "")),
                    r.get("editor_code", ""),
                    r.get("viewer_code", ""),
                    r.get("created_at", ""),
                    r.get("team_id"),
                ),
            )
        )
    if statements:
        sync_transaction(statements)


def append_team(r):
    owner_id = str(r.get("owner_id", ""))
    if not owner_id:
        raise ValueError("team owner_id is required")
    if not sync_one("users", "user_id=?", (owner_id,)):
        sync_execute(
            "INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)",
            (owner_id, "UTC", "jalali"),
        )
    sync_execute(
        """INSERT INTO teams(team_id,name,owner_id,editor_code,viewer_code,created_at)
        VALUES(?,?,?,?,?,?)""",
        (
            r["team_id"],
            r.get("name", ""),
            owner_id,
            r.get("editor_code", ""),
            r.get("viewer_code", ""),
            r.get("created_at", ""),
        ),
    )


def read_members():
    return sync_all("team_members")


def write_members(rows):
    """Synchronize the supplied member set for each affected team.

    The old implementation only appended/updated rows and could never remove
    a member after leave_team(). The database is now the source of truth.
    """
    affected = {str(r.get("team_id")) for r in rows if r.get("team_id")}
    if not affected:
        return

    existing = sync_all("team_members")
    by_team = {team_id: [] for team_id in affected}
    for row in rows:
        team_id = str(row.get("team_id"))
        if team_id in by_team:
            by_team[team_id].append(row)

    statements = []
    for team_id in affected:
        # Delete only members belonging to teams represented by this write.
        statements.append(("DELETE FROM team_members WHERE team_id=?", (team_id,)))
        for r in by_team[team_id]:
            uid = str(r.get("user_id", ""))
            if not uid:
                continue
            statements.append(
                (
                    """INSERT INTO team_members(
                        team_id,user_id,role,display_name,username,joined_at
                    ) VALUES(?,?,?,?,?,?)""",
                    (
                        team_id,
                        uid,
                        r.get("role", "viewer"),
                        r.get("display_name", ""),
                        r.get("username", ""),
                        r.get("joined_at", ""),
                    ),
                )
            )
    # Ensure users exist before FK inserts.
    for team_id in affected:
        for r in by_team[team_id]:
            uid = str(r.get("user_id", ""))
            if uid and not sync_one("users", "user_id=?", (uid,)):
                sync_execute(
                    "INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)",
                    (uid, "UTC", "jalali"),
                )
    sync_transaction(statements)


def append_member(r):
    team_id = str(r.get("team_id", ""))
    user_id = str(r.get("user_id", ""))
    if not team_id or not user_id:
        raise ValueError("team_id and user_id are required")
    if not sync_one("users", "user_id=?", (user_id,)):
        sync_execute(
            "INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)",
            (user_id, "UTC", "jalali"),
        )
    if not sync_one("teams", "team_id=?", (team_id,)):
        raise ValueError("team does not exist")
    sync_execute(
        """INSERT INTO team_members(team_id,user_id,role,display_name,username,joined_at)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(team_id,user_id) DO UPDATE SET
            role=excluded.role,
            display_name=excluded.display_name,
            username=excluded.username,
            joined_at=excluded.joined_at""",
        (
            team_id,
            user_id,
            r.get("role", "viewer"),
            r.get("display_name", ""),
            r.get("username", ""),
            r.get("joined_at", ""),
        ),
    )
