from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import shutil
import tempfile
from pathlib import Path

import aiosqlite

from services.database import DB_PATH, SCHEMA

DATA = Path("data")


def csv_rows(name: str):
    path = DATA / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def json_data(name: str, default):
    path = DATA / name
    if not path.exists():
        return default
    # A migration must never silently discard malformed source data.
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def text(value) -> str:
    return "" if value is None else str(value)


def integer(value, default=0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def boolean(value, default=False) -> int:
    if value is None or value == "":
        return int(default)
    if isinstance(value, bool):
        return int(value)
    return int(str(value).strip().lower() in {"1", "true", "yes", "y", "on"})


async def ensure_user(db, uid, name="", username=""):
    if uid is None or not text(uid):
        return
    await db.execute(
        """INSERT INTO users(user_id,full_name,username,timezone,date_format,messages_count)
        VALUES(?,?,?,?,?,0)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name=CASE WHEN excluded.full_name<>'' THEN excluded.full_name ELSE users.full_name END,
            username=CASE WHEN excluded.username<>'' THEN excluded.username ELSE users.username END""",
        (text(uid), text(name), text(username), "UTC", "jalali"),
    )


async def migrate(output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)

    # Build into a temporary SQLite file first. A failed migration can therefore
    # never leave a half-imported production database.
    fd, temp_name = tempfile.mkstemp(prefix="migration-", suffix=".db", dir=str(output.parent))
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        async with aiosqlite.connect(temp_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.executescript(SCHEMA)
            await db.execute("BEGIN IMMEDIATE")
            try:
                for r in csv_rows("users.csv"):
                    uid = text(r.get("user_id"))
                    if not uid:
                        continue
                    await db.execute(
                        """INSERT INTO users(user_id,full_name,username,timezone,date_format,first_seen,last_seen,messages_count)
                        VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            full_name=excluded.full_name, username=excluded.username,
                            timezone=excluded.timezone, date_format=excluded.date_format,
                            first_seen=excluded.first_seen, last_seen=excluded.last_seen,
                            messages_count=excluded.messages_count""",
                        (
                            uid,
                            r.get("full_name", ""),
                            r.get("username", ""),
                            r.get("timezone") or "UTC",
                            r.get("date_format") or "jalali",
                            text(r.get("first_seen")),
                            text(r.get("last_seen")),
                            integer(r.get("messages_count")),
                        ),
                    )

                for r in csv_rows("teams.csv"):
                    await ensure_user(db, r.get("owner_id"))
                    await db.execute(
                        """INSERT INTO teams(team_id,name,owner_id,editor_code,viewer_code,created_at)
                        VALUES(?,?,?,?,?,?)""",
                        (
                            text(r.get("team_id")),
                            r.get("name", ""),
                            text(r.get("owner_id")),
                            r.get("editor_code", ""),
                            r.get("viewer_code", ""),
                            text(r.get("created_at")),
                        ),
                    )

                for r in csv_rows("team_members.csv"):
                    await ensure_user(db, r.get("user_id"), r.get("display_name", ""), r.get("username", ""))
                    await db.execute(
                        """INSERT INTO team_members(team_id,user_id,role,display_name,username,joined_at)
                        VALUES(?,?,?,?,?,?)""",
                        (
                            text(r.get("team_id")),
                            text(r.get("user_id")),
                            r.get("role") or "viewer",
                            r.get("display_name", ""),
                            r.get("username", ""),
                            text(r.get("joined_at")),
                        ),
                    )

                for r in csv_rows("tasks.csv"):
                    await ensure_user(db, r.get("user_id"))
                    await ensure_user(db, r.get("assignee_id"), r.get("assignee_name", ""), r.get("assignee_username", ""))
                    task_id = text(r.get("id"))
                    if not task_id:
                        raise ValueError("tasks.csv contains a task without id")
                    await db.execute(
                        """INSERT INTO tasks(
                            id,bot_key,user_id,title,priority,status,deadline,category,tags,description,
                            created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username,
                            jira_key,jira_sync_hash
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            task_id,
                            r.get("bot_key") or "default",
                            text(r.get("user_id")),
                            r.get("title", ""),
                            r.get("priority") or "medium",
                            r.get("status") or "pending",
                            text(r.get("deadline")),
                            r.get("category", ""),
                            r.get("tags", ""),
                            r.get("description", ""),
                            text(r.get("created_at")),
                            text(r.get("completed_at")),
                            r.get("team_id") or None,
                            r.get("assignee_id") or None,
                            r.get("assignee_name", ""),
                            r.get("assignee_username", ""),
                            r.get("jira_key", ""),
                            r.get("jira_sync_hash", ""),
                        ),
                    )

                    # Legacy assignment history was stored inline. Preserve every
                    # record as a row instead of retaining the serialized field.
                    raw_history = r.get("assignment_history") or ""
                    for line in raw_history.splitlines():
                        parts = line.split("|", 4)
                        if len(parts) != 5:
                            continue
                        ts, actor, action, old_name, new_name = parts
                        await ensure_user(db, actor)
                        await db.execute(
                            """INSERT INTO task_assignment_history(
                                task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at
                            ) VALUES(?,?,?,?,?,?)""",
                            (task_id, text(actor), action, old_name, new_name, ts),
                        )

                    try:
                        comments = json.loads(r.get("comments") or "[]")
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid comments JSON for task {task_id}") from exc
                    if not isinstance(comments, list):
                        raise ValueError(f"comments for task {task_id} is not a list")
                    for comment in comments:
                        if not isinstance(comment, dict):
                            raise ValueError(f"Invalid comment record for task {task_id}")
                        author_id = comment.get("author_id") or comment.get("user_id")
                        await ensure_user(db, author_id, comment.get("author_name", ""), comment.get("author_username", ""))
                        meta = {
                            key: value
                            for key, value in comment.items()
                            if key not in {"author_id", "user_id", "author_name", "author_username", "created_at"}
                        }
                        await db.execute(
                            """INSERT INTO task_comments(
                                task_id,author_id,author_name,author_username,content_json,created_at
                            ) VALUES(?,?,?,?,?,?)""",
                            (
                                task_id,
                                text(author_id) if author_id else None,
                                comment.get("author_name", ""),
                                comment.get("author_username", ""),
                                json.dumps(meta, ensure_ascii=False),
                                text(comment.get("created_at")),
                            ),
                        )

                for r in csv_rows("habits.csv"):
                    await ensure_user(db, r.get("user_id"))
                    await db.execute(
                        """INSERT INTO habits(
                            id,user_id,title,category,description,repeat_type,target,reminder_time,
                            start_date,active,created_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            text(r.get("id")),
                            text(r.get("user_id")),
                            r.get("title", ""),
                            r.get("category", ""),
                            r.get("description", ""),
                            r.get("repeat_type") or "daily",
                            r.get("target", ""),
                            r.get("reminder_time", ""),
                            text(r.get("start_date")),
                            boolean(r.get("active"), True),
                            text(r.get("created_at")),
                        ),
                    )

                for r in csv_rows("habit_logs.csv"):
                    await ensure_user(db, r.get("user_id"))
                    await db.execute(
                        """INSERT OR IGNORE INTO habit_logs(habit_id,user_id,done_date,done_at)
                        VALUES(?,?,?,?)""",
                        (text(r.get("habit_id")), text(r.get("user_id")), text(r.get("done_date")), text(r.get("done_at"))),
                    )

                for r in csv_rows("custom_bots.csv"):
                    await ensure_user(db, r.get("owner_user_id"), r.get("owner_name", ""), r.get("owner_username", ""))
                    await db.execute(
                        """INSERT INTO custom_bots(
                            bot_key,owner_user_id,owner_name,owner_username,bot_token,bot_username,
                            features,status,pricing_plan,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            text(r.get("bot_key")),
                            text(r.get("owner_user_id")) or None,
                            r.get("owner_name", ""),
                            r.get("owner_username", ""),
                            r.get("bot_token", ""),
                            r.get("bot_username", ""),
                            r.get("features", ""),
                            r.get("status") or "active",
                            r.get("pricing_plan") or "free_beta",
                            text(r.get("created_at")),
                            text(r.get("updated_at")),
                        ),
                    )

                for r in csv_rows("integrations.csv"):
                    await ensure_user(db, r.get("user_id"))
                    await db.execute(
                        """INSERT INTO external_connections(
                            user_id,bot_key,provider,access_token,refresh_token,expires_at,
                            external_list_id,external_list_name,enabled,last_sync
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (
                            text(r.get("user_id")),
                            r.get("bot_key") or "default",
                            r.get("provider", ""),
                            r.get("access_token", ""),
                            r.get("refresh_token", ""),
                            r.get("expires_at", ""),
                            r.get("external_list_id", ""),
                            r.get("external_list_name", ""),
                            boolean(r.get("enabled")),
                            r.get("last_sync", ""),
                        ),
                    )

                for r in json_data("jira_connections.json", []):
                    await ensure_user(db, r.get("user_id"))
                    await db.execute(
                        """INSERT INTO jira_connections(
                            bot_key,user_id,base_url,identity,credential,project_key,deployment,
                            issue_type,account_id,auth_method,connected_at,last_sync_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            r.get("bot_key") or "default",
                            text(r.get("user_id")),
                            r.get("base_url", ""),
                            r.get("identity", ""),
                            r.get("credential", ""),
                            r.get("project_key", ""),
                            r.get("deployment") or "cloud",
                            r.get("issue_type") or "Task",
                            r.get("account_id", ""),
                            r.get("auth_method") or "basic",
                            text(r.get("connected_at")),
                            text(r.get("last_sync_at")),
                        ),
                    )

                for r in json_data("jira_task_links.json", []):
                    await db.execute(
                        """INSERT INTO jira_task_links(bot_key,task_id,jira_key,sync_hash,updated_at)
                        VALUES(?,?,?,?,?)""",
                        (
                            r.get("bot_key") or "default",
                            r.get("task_id"),
                            r.get("jira_key"),
                            r.get("sync_hash", ""),
                            text(r.get("updated_at")),
                        ),
                    )

                business = json_data("business_connections.json", {})
                for r in (business.get("connections") or {}).values():
                    await ensure_user(db, r.get("user_id"), r.get("full_name", ""), r.get("username", ""))
                    await db.execute(
                        """INSERT INTO business_connections(
                            id,user_id,user_chat_id,username,full_name,date,can_reply,is_enabled,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (
                            r.get("id"),
                            text(r.get("user_id")) if r.get("user_id") is not None else None,
                            text(r.get("user_chat_id")),
                            r.get("username", ""),
                            r.get("full_name", ""),
                            text(r.get("date")),
                            boolean(r.get("can_reply")),
                            boolean(r.get("is_enabled")),
                            text(r.get("updated_at")),
                        ),
                    )

                for r in business.get("messages") or []:
                    await ensure_user(db, r.get("from_user_id"), "", r.get("from_username", ""))
                    await db.execute(
                        """INSERT INTO business_messages(
                            event_type,business_connection_id,chat_id,message_id,from_user_id,
                            from_username,text,message_ids_json,date,recorded_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (
                            r.get("event_type", ""),
                            r.get("business_connection_id"),
                            text(r.get("chat_id")),
                            text(r.get("message_id")),
                            text(r.get("from_user_id")) if r.get("from_user_id") is not None else None,
                            r.get("from_username", ""),
                            r.get("text", ""),
                            json.dumps(r.get("message_ids", []), ensure_ascii=False),
                            text(r.get("date")),
                            text(r.get("recorded_at")),
                        ),
                    )

                await db.commit()
            except Exception:
                await db.rollback()
                raise

        if output.exists():
            raise FileExistsError(f"Target already exists: {output}; use --force to replace it")
        os.replace(temp_path, output)
    finally:
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-time CSV/JSON to SQLite migration")
    parser.add_argument(
        "--output",
        default=str(DB_PATH),
        help="SQLite output path (default: data/data.db)",
    )
    parser.add_argument("--backup", action="store_true", help="Backup an existing output before --force replacement")
    parser.add_argument("--force", action="store_true", help="Replace an existing output database")
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit(f"Target already exists: {output}. Use --force for replacement.")
    if args.backup and output.exists():
        shutil.copy2(output, output.with_suffix(output.suffix + ".bak"))
    asyncio.run(migrate(output))
    print(f"Migration complete: {output}")
