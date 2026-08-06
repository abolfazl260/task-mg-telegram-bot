"""CSV storage for teams and memberships."""

import csv
import os

TEAMS_PATH = "data/teams.csv"
MEMBERS_PATH = "data/team_members.csv"

TEAM_HEADERS = [
    "team_id",
    "name",
    "owner_id",
    "editor_code",
    "viewer_code",
    "created_at",
]

MEMBER_HEADERS = [
    "team_id",
    "user_id",
    "role",  # owner | editor | viewer
    "display_name",
    "username",
    "joined_at",
]


def _ensure_file(path, headers):
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)
        return

    # migrate missing columns
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        old_fields = list(reader.fieldnames or [])
        rows = list(reader)

    missing = [h for h in headers if h not in old_fields]
    if missing:
        for row in rows:
            for h in headers:
                row.setdefault(h, "")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow({h: row.get(h, "") for h in headers})


def init_teams():
    _ensure_file(TEAMS_PATH, TEAM_HEADERS)
    _ensure_file(MEMBERS_PATH, MEMBER_HEADERS)


def read_teams():
    _ensure_file(TEAMS_PATH, TEAM_HEADERS)
    with open(TEAMS_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for h in TEAM_HEADERS:
            r.setdefault(h, "")
    return rows


def write_teams(rows):
    with open(TEAMS_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TEAM_HEADERS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in TEAM_HEADERS})


def append_team(row: dict):
    _ensure_file(TEAMS_PATH, TEAM_HEADERS)
    with open(TEAMS_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TEAM_HEADERS, extrasaction="ignore")
        w.writerow({h: row.get(h, "") for h in TEAM_HEADERS})


def read_members():
    _ensure_file(MEMBERS_PATH, MEMBER_HEADERS)
    with open(MEMBERS_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for h in MEMBER_HEADERS:
            r.setdefault(h, "")
    return rows


def write_members(rows):
    with open(MEMBERS_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MEMBER_HEADERS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in MEMBER_HEADERS})


def append_member(row: dict):
    _ensure_file(MEMBERS_PATH, MEMBER_HEADERS)
    with open(MEMBERS_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MEMBER_HEADERS, extrasaction="ignore")
        w.writerow({h: row.get(h, "") for h in MEMBER_HEADERS})
