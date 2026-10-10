from __future__ import annotations

import asyncio
import atexit
import logging
import sqlite3
import threading
import time
from pathlib import Path

import aiosqlite

from services.operations.schema import migrate as migrate_operations

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = (BASE_DIR / "data" / "data.db").resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
SQLITE_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_MAX_RETRIES = 6
logger = logging.getLogger(__name__)
SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 30000;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'UTC', date_format TEXT NOT NULL DEFAULT 'jalali',
    first_seen TEXT NOT NULL DEFAULT '', last_seen TEXT NOT NULL DEFAULT '', messages_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY, name TEXT NOT NULL, owner_id TEXT NOT NULL REFERENCES users(user_id),
    editor_code TEXT NOT NULL UNIQUE, viewer_code TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS team_members (
    team_id TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL, display_name TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '', joined_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(team_id,user_id)
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default', work_item_type TEXT NOT NULL DEFAULT 'task', parent_task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'medium', status TEXT NOT NULL DEFAULT 'pending', deadline TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT '',
    completed_at TEXT NOT NULL DEFAULT '', team_id TEXT REFERENCES teams(team_id) ON DELETE SET NULL,
    assignee_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, assignee_name TEXT NOT NULL DEFAULT '', assignee_username TEXT NOT NULL DEFAULT '',
    jira_key TEXT NOT NULL DEFAULT '', jira_sync_hash TEXT NOT NULL DEFAULT '',
    workspace_id TEXT REFERENCES workspaces(id), unit_id TEXT REFERENCES workspace_units(id),
    reference_id TEXT REFERENCES reference_entities(id), case_id TEXT REFERENCES cases(id),
    outcome_id TEXT REFERENCES outcomes(id), workflow_instance_id TEXT REFERENCES workflow_instances(id),
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, author_name TEXT NOT NULL DEFAULT '', author_username TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT '',
    bot_key TEXT NOT NULL DEFAULT 'default', source TEXT NOT NULL DEFAULT 'core', source_key TEXT,
    telegram_chat_id TEXT, telegram_message_id INTEGER
);
CREATE TABLE IF NOT EXISTS task_assignment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    actor_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, action TEXT NOT NULL DEFAULT '', old_assignee_name TEXT NOT NULL DEFAULT '',
    new_assignee_name TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT ''
);
-- Stable creation request identity, committed atomically with the task.
-- Existing tasks require no backfill; historical rows remain unchanged.
CREATE TABLE IF NOT EXISTS task_creation_requests (
    request_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_task_creation_requests_task ON task_creation_requests(task_id);

CREATE TABLE IF NOT EXISTS habits (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', repeat_type TEXT NOT NULL DEFAULT 'daily', target TEXT NOT NULL DEFAULT '',
    reminder_time TEXT NOT NULL DEFAULT '', start_date TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS habit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, done_date TEXT NOT NULL, done_at TEXT NOT NULL DEFAULT '',
    UNIQUE(habit_id,user_id,done_date)
);
CREATE TABLE IF NOT EXISTS external_connections (
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, bot_key TEXT NOT NULL, provider TEXT NOT NULL,
    access_token TEXT NOT NULL DEFAULT '', refresh_token TEXT NOT NULL DEFAULT '', expires_at TEXT NOT NULL DEFAULT '',
    external_list_id TEXT NOT NULL DEFAULT '', external_list_name TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 0,
    last_sync TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id,bot_key,provider)
);
CREATE TABLE IF NOT EXISTS oauth_pending_states (
    state TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    user_id TEXT NOT NULL,
    bot_key TEXT NOT NULL DEFAULT 'default',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS external_task_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    bot_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    local_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    external_task_id TEXT NOT NULL,
    external_list_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    UNIQUE(user_id,bot_key,provider,local_task_id),
    UNIQUE(user_id,bot_key,provider,external_task_id)
);
CREATE TABLE IF NOT EXISTS jira_connections (
    bot_key TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, base_url TEXT NOT NULL,
    identity TEXT NOT NULL DEFAULT '', credential TEXT NOT NULL DEFAULT '', project_key TEXT NOT NULL, deployment TEXT NOT NULL DEFAULT 'cloud',
    issue_type TEXT NOT NULL DEFAULT 'Task', account_id TEXT NOT NULL DEFAULT '', auth_method TEXT NOT NULL DEFAULT 'basic',
    connected_at TEXT NOT NULL DEFAULT '', last_sync_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(bot_key,user_id)
);
CREATE TABLE IF NOT EXISTS jira_task_links (
    bot_key TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE, jira_key TEXT NOT NULL,
    sync_hash TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(bot_key,task_id), UNIQUE(bot_key,jira_key)
);
CREATE TABLE IF NOT EXISTS custom_bots (
    bot_key TEXT PRIMARY KEY, owner_user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE, owner_name TEXT NOT NULL DEFAULT '',
    owner_username TEXT NOT NULL DEFAULT '', bot_token TEXT NOT NULL DEFAULT '', bot_username TEXT NOT NULL DEFAULT '', features TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active', pricing_plan TEXT NOT NULL DEFAULT 'free_beta', created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS business_connections (
    id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL, user_chat_id TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL DEFAULT '', date TEXT NOT NULL DEFAULT '', can_reply INTEGER NOT NULL DEFAULT 0, is_enabled INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS business_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL DEFAULT '', business_connection_id TEXT REFERENCES business_connections(id) ON DELETE CASCADE,
    chat_id TEXT NOT NULL DEFAULT '', message_id TEXT NOT NULL DEFAULT '', from_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
    from_username TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', message_ids_json TEXT NOT NULL DEFAULT '[]', date TEXT NOT NULL DEFAULT '', recorded_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS task_attribute_definitions (
    id TEXT PRIMARY KEY,
    bot_key TEXT NOT NULL DEFAULT 'default',
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
    work_item_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    data_type TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 0 CHECK(required IN (0,1)),
    repeatable INTEGER NOT NULL DEFAULT 0 CHECK(repeatable IN (0,1)),
    default_value_json TEXT,
    validation_json TEXT NOT NULL DEFAULT '{}',
    searchable INTEGER NOT NULL DEFAULT 0 CHECK(searchable IN (0,1)),
    filterable INTEGER NOT NULL DEFAULT 0 CHECK(filterable IN (0,1)),
    sortable INTEGER NOT NULL DEFAULT 0 CHECK(sortable IN (0,1)),
    group_key TEXT NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    sensitive INTEGER NOT NULL DEFAULT 0 CHECK(sensitive IN (0,1)),
    view_roles_json TEXT NOT NULL DEFAULT '[]',
    edit_roles_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(bot_key, workspace_id, work_item_type, field_key, version)
);
CREATE TABLE IF NOT EXISTS task_attribute_values (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    definition_id TEXT NOT NULL REFERENCES task_attribute_definitions(id) ON DELETE RESTRICT,
    definition_version INTEGER NOT NULL DEFAULT 1,
    ordinal INTEGER NOT NULL DEFAULT 0 CHECK(ordinal >= 0),
    value_text TEXT,
    value_number REAL,
    value_boolean INTEGER CHECK(value_boolean IN (0,1)),
    value_date TEXT,
    value_datetime TEXT,
    value_json TEXT,
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    UNIQUE(task_id, definition_id, ordinal)
);
CREATE TABLE IF NOT EXISTS task_attribute_audit (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    definition_id TEXT NOT NULL REFERENCES task_attribute_definitions(id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL, action TEXT NOT NULL, old_value_hash TEXT NOT NULL DEFAULT '', new_value_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS task_contact_points (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK(type IN ('phone','email','address','other')),
    label TEXT NOT NULL DEFAULT '',
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_key ON tasks(bot_key);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_user ON tasks(bot_key,user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_status ON tasks(bot_key,status);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON tasks(team_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee_id ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_comments_task_id ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_assignment_task_id ON task_assignment_history(task_id);
CREATE INDEX IF NOT EXISTS idx_members_user_id ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_habits_user_id ON habits(user_id);
CREATE INDEX IF NOT EXISTS idx_habit_logs_user_date ON habit_logs(user_id,done_date);
CREATE INDEX IF NOT EXISTS idx_jira_links_key ON jira_task_links(jira_key);
CREATE INDEX IF NOT EXISTS idx_oauth_pending_created_at ON oauth_pending_states(created_at);
CREATE INDEX IF NOT EXISTS idx_business_messages_connection ON business_messages(business_connection_id);
CREATE INDEX IF NOT EXISTS idx_attribute_definitions_lookup ON task_attribute_definitions(bot_key, workspace_id, work_item_type, active, display_order);
CREATE INDEX IF NOT EXISTS idx_attribute_definitions_search ON task_attribute_definitions(searchable, filterable, sortable);
CREATE INDEX IF NOT EXISTS idx_attribute_values_task ON task_attribute_values(task_id, definition_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_attribute_values_text ON task_attribute_values(definition_id, value_text);
CREATE INDEX IF NOT EXISTS idx_attribute_values_number ON task_attribute_values(definition_id, value_number);
CREATE INDEX IF NOT EXISTS idx_attribute_values_date ON task_attribute_values(definition_id, value_date);
CREATE TABLE IF NOT EXISTS task_view_schemas (
    id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default', workspace_id TEXT,
    work_item_type TEXT NOT NULL,
    schema_kind TEXT NOT NULL CHECK(schema_kind IN ('create','edit','detail','list')),
    schema_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '',
    UNIQUE(bot_key,workspace_id,work_item_type,schema_kind,version)
);
CREATE INDEX IF NOT EXISTS idx_task_view_schemas_lookup ON task_view_schemas(bot_key,workspace_id,work_item_type,schema_kind,active,version);
CREATE INDEX IF NOT EXISTS idx_contact_points_task ON task_contact_points(task_id, type, status);
CREATE INDEX IF NOT EXISTS idx_contact_points_normalized ON task_contact_points(normalized_value, type);
CREATE INDEX IF NOT EXISTS idx_task_attribute_audit_task ON task_attribute_audit(task_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contact_points_primary ON task_contact_points(task_id, type) WHERE is_primary=1 AND status='active';

-- Attachments are metadata-only references to the configured file backend.  The
-- parent task is the authorization boundary; attribute links are optional.
CREATE TABLE IF NOT EXISTS task_attachments (
    id TEXT PRIMARY KEY,
    bot_key TEXT NOT NULL DEFAULT 'default',
    workspace_id TEXT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    attribute_definition_id TEXT REFERENCES task_attribute_definitions(id) ON DELETE SET NULL,
    attribute_ordinal INTEGER NOT NULL DEFAULT 0 CHECK(attribute_ordinal >= 0),
    file_id TEXT NOT NULL,
    storage_key TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL DEFAULT '',
    media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK(size_bytes >= 0),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    archived_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(bot_key, id)
);
CREATE INDEX IF NOT EXISTS idx_task_attachments_task ON task_attachments(task_id, archived_at, created_at);
CREATE INDEX IF NOT EXISTS idx_task_attachments_attribute ON task_attachments(attribute_definition_id, task_id, archived_at);

CREATE TABLE IF NOT EXISTS report_definitions (
    id TEXT PRIMARY KEY,
    bot_key TEXT NOT NULL DEFAULT 'default',
    workspace_id TEXT,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    source_item_type TEXT NOT NULL,
    filters_json TEXT NOT NULL DEFAULT '{}',
    group_by TEXT NOT NULL DEFAULT '',
    date_field TEXT NOT NULL DEFAULT 'created_at',
    metric TEXT NOT NULL DEFAULT 'count',
    label TEXT NOT NULL DEFAULT '',
    role_permissions_json TEXT NOT NULL DEFAULT '[]',
    branch_scope TEXT NOT NULL DEFAULT 'any',
    drill_down_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(bot_key, workspace_id, name, version)
);
CREATE INDEX IF NOT EXISTS idx_report_definitions_scope ON report_definitions(bot_key, workspace_id, active, source_item_type);

CREATE TABLE IF NOT EXISTS typed_work_item_data (
    task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    data_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_typed_work_item_data_updated ON typed_work_item_data(updated_at);

CREATE TABLE IF NOT EXISTS typed_migration_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('running','completed','rolled_back','failed')),
    backup_reference TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS typed_migration_map (
    run_id TEXT NOT NULL REFERENCES typed_migration_runs(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    legacy_kind TEXT NOT NULL,
    legacy_id TEXT NOT NULL,
    typed_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    PRIMARY KEY(run_id, legacy_kind, legacy_id),
    UNIQUE(workspace_id, legacy_kind, legacy_id)
);
CREATE INDEX IF NOT EXISTS idx_typed_migration_task ON typed_migration_map(typed_task_id);
"""

CORE_SCHEMA = SCHEMA


async def migrate_core_schema(conn) -> None:
    """Apply additive migrations required before post-schema indexes exist."""
    async with conn.execute("PRAGMA table_info(tasks)") as cursor:
        task_columns = {row[1] for row in await cursor.fetchall()}
    if "work_item_type" not in task_columns:
        await conn.execute(
            "ALTER TABLE tasks ADD COLUMN work_item_type TEXT NOT NULL DEFAULT 'task'"
        )
    await conn.execute(
        "UPDATE tasks SET work_item_type='task' "
        "WHERE work_item_type IS NULL OR TRIM(work_item_type)=''"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_work_item_type ON tasks(work_item_type)"
    )

    # Parent/child hierarchy is additive so existing installations keep all
    # legacy tasks as roots (parent_task_id IS NULL).
    if "parent_task_id" not in task_columns:
        await conn.execute(
            "ALTER TABLE tasks ADD COLUMN parent_task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL"
        )
    async with conn.execute("PRAGMA table_info(tasks)") as cursor:
        task_columns = {row[1] for row in await cursor.fetchall()}
    if "archived_at" not in task_columns:
        await conn.execute("ALTER TABLE tasks ADD COLUMN archived_at TEXT")
    if "created_at" in task_columns:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id, created_at, id)")
    else:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id, id)")
    if "workspace_id" in task_columns:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_workspace_parent ON tasks(workspace_id, parent_task_id, id)")
    await conn.execute("DROP TRIGGER IF EXISTS task_parent_scope_insert")
    await conn.execute("DROP TRIGGER IF EXISTS task_parent_scope_update")
    parent_trigger = """
    CREATE TRIGGER task_parent_scope_{operation}
    BEFORE {verb} ON tasks
    WHEN NEW.parent_task_id IS NOT NULL
    BEGIN
      SELECT CASE WHEN NEW.parent_task_id = NEW.id
        THEN RAISE(ABORT, 'task_parent_self_reference') END;
      SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM tasks p WHERE p.id=NEW.parent_task_id)
        THEN RAISE(ABORT, 'task_parent_not_found') END;
      SELECT CASE WHEN EXISTS (
          SELECT 1 FROM tasks p WHERE p.id=NEW.parent_task_id
            AND (p.workspace_id IS NOT NEW.workspace_id
              OR (p.workspace_id IS NULL AND p.user_id IS NOT NEW.user_id))
        ) THEN RAISE(ABORT, 'task_parent_scope_mismatch') END;
    END;
    """
    await conn.executescript(parent_trigger.format(operation="insert", verb="INSERT") + parent_trigger.format(operation="update", verb="UPDATE"))
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS task_attribute_definitions (
            id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default', workspace_id TEXT,
            work_item_type TEXT NOT NULL, field_key TEXT NOT NULL, label TEXT NOT NULL,
            data_type TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 0, repeatable INTEGER NOT NULL DEFAULT 0,
            default_value_json TEXT, validation_json TEXT NOT NULL DEFAULT '{}',
            searchable INTEGER NOT NULL DEFAULT 0, filterable INTEGER NOT NULL DEFAULT 0, sortable INTEGER NOT NULL DEFAULT 0,
            group_key TEXT NOT NULL DEFAULT '', display_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(bot_key, workspace_id, work_item_type, field_key, version)
        )"""
    )
    async with conn.execute("PRAGMA table_info(task_attribute_definitions)") as cursor:
        attribute_columns = {row[1] for row in await cursor.fetchall()}
    for name, statement in (("sensitive", "ALTER TABLE task_attribute_definitions ADD COLUMN sensitive INTEGER NOT NULL DEFAULT 0"), ("view_roles_json", "ALTER TABLE task_attribute_definitions ADD COLUMN view_roles_json TEXT NOT NULL DEFAULT '[]'"), ("edit_roles_json", "ALTER TABLE task_attribute_definitions ADD COLUMN edit_roles_json TEXT NOT NULL DEFAULT '[]'")):
        if name in attribute_columns:
            continue
        await conn.execute(statement)
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_attribute_definitions (
            id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default',
            workspace_id TEXT, work_item_type TEXT NOT NULL, field_key TEXT NOT NULL,
            label TEXT NOT NULL, data_type TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 0 CHECK(required IN (0,1)),
            repeatable INTEGER NOT NULL DEFAULT 0 CHECK(repeatable IN (0,1)),
            default_value_json TEXT, validation_json TEXT NOT NULL DEFAULT '{}',
            sensitive INTEGER NOT NULL DEFAULT 0, view_roles_json TEXT NOT NULL DEFAULT '[]', edit_roles_json TEXT NOT NULL DEFAULT '[]',
            searchable INTEGER NOT NULL DEFAULT 0 CHECK(searchable IN (0,1)),
            filterable INTEGER NOT NULL DEFAULT 0 CHECK(filterable IN (0,1)),
            sortable INTEGER NOT NULL DEFAULT 0 CHECK(sortable IN (0,1)),
            group_key TEXT NOT NULL DEFAULT '', display_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
            created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(bot_key, workspace_id, work_item_type, field_key, version)
        );
        CREATE TABLE IF NOT EXISTS task_attribute_audit (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE, definition_id TEXT NOT NULL REFERENCES task_attribute_definitions(id) ON DELETE CASCADE, actor_id TEXT NOT NULL, action TEXT NOT NULL, old_value_hash TEXT NOT NULL DEFAULT '', new_value_hash TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_task_attribute_audit_task ON task_attribute_audit(task_id, created_at);
        CREATE TABLE IF NOT EXISTS task_attribute_values (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            definition_id TEXT NOT NULL REFERENCES task_attribute_definitions(id) ON DELETE RESTRICT,
            definition_version INTEGER NOT NULL DEFAULT 1, ordinal INTEGER NOT NULL DEFAULT 0 CHECK(ordinal >= 0),
            value_text TEXT, value_number REAL, value_boolean INTEGER CHECK(value_boolean IN (0,1)),
            value_date TEXT, value_datetime TEXT, value_json TEXT,
            created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(task_id, definition_id, ordinal)
        );
        CREATE TABLE IF NOT EXISTS task_contact_points (
            id TEXT PRIMARY KEY, workspace_id TEXT, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            type TEXT NOT NULL CHECK(type IN ('phone','email','address','other')), label TEXT NOT NULL DEFAULT '',
            value TEXT NOT NULL, normalized_value TEXT NOT NULL, is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
            note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
            created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_attribute_definitions_lookup ON task_attribute_definitions(bot_key, workspace_id, work_item_type, active, display_order);
        CREATE INDEX IF NOT EXISTS idx_attribute_definitions_search ON task_attribute_definitions(searchable, filterable, sortable);
        CREATE INDEX IF NOT EXISTS idx_attribute_values_task ON task_attribute_values(task_id, definition_id, ordinal);
        CREATE INDEX IF NOT EXISTS idx_attribute_values_text ON task_attribute_values(definition_id, value_text);
        CREATE INDEX IF NOT EXISTS idx_attribute_values_number ON task_attribute_values(definition_id, value_number);
        CREATE INDEX IF NOT EXISTS idx_attribute_values_date ON task_attribute_values(definition_id, value_date);
        CREATE TABLE IF NOT EXISTS task_view_schemas (
            id TEXT PRIMARY KEY, bot_key TEXT NOT NULL DEFAULT 'default', workspace_id TEXT,
            work_item_type TEXT NOT NULL,
            schema_kind TEXT NOT NULL CHECK(schema_kind IN ('create','edit','detail','list')),
            schema_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(bot_key,workspace_id,work_item_type,schema_kind,version)
        );
        CREATE INDEX IF NOT EXISTS idx_task_view_schemas_lookup ON task_view_schemas(bot_key,workspace_id,work_item_type,schema_kind,active,version);
        CREATE INDEX IF NOT EXISTS idx_contact_points_task ON task_contact_points(task_id, type, status);
        CREATE INDEX IF NOT EXISTS idx_contact_points_normalized ON task_contact_points(normalized_value, type);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_contact_points_primary ON task_contact_points(task_id, type) WHERE is_primary=1 AND status='active';
        """
    )

    async with conn.execute("PRAGMA table_info(task_comments)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}

    additions = (
        ("bot_key", "ALTER TABLE task_comments ADD COLUMN bot_key TEXT NOT NULL DEFAULT 'default'"),
        ("source", "ALTER TABLE task_comments ADD COLUMN source TEXT NOT NULL DEFAULT 'core'"),
        ("source_key", "ALTER TABLE task_comments ADD COLUMN source_key TEXT"),
        ("telegram_chat_id", "ALTER TABLE task_comments ADD COLUMN telegram_chat_id TEXT"),
        ("telegram_message_id", "ALTER TABLE task_comments ADD COLUMN telegram_message_id INTEGER"),
    )
    for name, statement in additions:
        if name not in columns:
            await conn.execute(statement)

    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_comments_source_key "
        "ON task_comments(source_key)"
    )
    await conn.commit()


class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None
        self.lock = asyncio.Lock()
        self.initialized = False

    async def connect(self):
        if self.conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = await aiosqlite.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys=ON")
            await self.conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
            await self.conn.execute("PRAGMA journal_mode=WAL")
            await self.conn.execute("PRAGMA synchronous=NORMAL")
        if not self.initialized:
            await self.conn.executescript(CORE_SCHEMA)
            await migrate_core_schema(self.conn)
            await migrate_operations(self.conn)
            await self.conn.commit()
            self.initialized = True
        return self.conn

    async def close(self):
        if self.conn is not None:
            conn = self.conn
            self.conn = None
            self.initialized = False
            await conn.close()

_db_by_loop: dict[asyncio.AbstractEventLoop, Database] = {}
_sync_loop: asyncio.AbstractEventLoop | None = None
_sync_thread: threading.Thread | None = None
_sync_loop_ready = threading.Event()
_sync_loop_lock = threading.Lock()

async def get_db() -> Database:
    loop = asyncio.get_running_loop()
    db = _db_by_loop.get(loop)
    if db is None:
        db = Database()
        _db_by_loop[loop] = db
    await db.connect()
    return db

async def init_db():
    await get_db()

async def close_db():
    loop = asyncio.get_running_loop()
    db = _db_by_loop.pop(loop, None)
    if db is not None:
        await db.close()

async def close_all_dbs():
    dbs = list(_db_by_loop.values())
    _db_by_loop.clear()
    for db in dbs:
        try:
            await db.close()
        except Exception:
            logger.exception("database_close_failed operation=close_all_dbs")

def _start_sync_loop() -> asyncio.AbstractEventLoop:
    global _sync_loop, _sync_thread
    with _sync_loop_lock:
        if _sync_loop is not None and _sync_loop.is_running():
            return _sync_loop
        _sync_loop_ready.clear()
        def runner():
            global _sync_loop
            loop = asyncio.new_event_loop()
            _sync_loop = loop
            asyncio.set_event_loop(loop)
            _sync_loop_ready.set()
            try:
                loop.run_forever()
            finally:
                try:
                    loop.run_until_complete(close_all_dbs())
                except Exception:
                    logger.exception("database_close_failed operation=sync_loop_finalizer")
                loop.close()
        _sync_thread = threading.Thread(target=runner, name="db-sync-loop", daemon=True)
        _sync_thread.start()
    if not _sync_loop_ready.wait(timeout=10):
        raise RuntimeError("Timed out starting database compatibility event loop")
    if _sync_loop is None:
        raise RuntimeError("Database compatibility event loop failed to start")
    return _sync_loop

def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        async def runner_without_existing_loop():
            try:
                return await coro
            finally:
                await close_db()
        return asyncio.run(runner_without_existing_loop())
    loop = _start_sync_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

def shutdown_sync_loop() -> None:
    global _sync_loop, _sync_thread
    with _sync_loop_lock:
        loop, thread = _sync_loop, _sync_thread
        _sync_loop = None
        _sync_thread = None
    if loop is None:
        return
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(close_all_dbs(), loop)
        try:
            future.result(timeout=10)
        finally:
            loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread.is_alive():
        thread.join(timeout=10)

async def fetch_all(table, where="", params=()):
    db = await get_db()
    q = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
    async with db.conn.execute(q, tuple(params)) as cur:
        return [dict(r) for r in await cur.fetchall()]

async def fetch_one(table, where, params=()):
    rows = await fetch_all(table, where, params)
    return rows[0] if rows else None

async def execute(sql, params=()):
    db = await get_db()
    async with db.lock:
        cur = await db.conn.execute(sql, tuple(params))
        await db.conn.commit()
        return cur.lastrowid

async def execute_returning_one(sql, params=()):
    db = await get_db()
    async with db.lock:
        cur = await db.conn.execute(sql, tuple(params))
        row = await cur.fetchone()
        await db.conn.commit()
        return dict(row) if row else None

async def execute_many(sql, rows):
    db = await get_db()
    async with db.lock:
        await db.conn.executemany(sql, [tuple(r) for r in rows])
        await db.conn.commit()

def _is_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and any(marker in str(exc).lower() for marker in ("database is locked", "database table is locked", "database is busy"))

def _retry_delay(attempt: int) -> float:
    return min(0.25 * (2 ** attempt), 4.0)

def _configure_sync_connection(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

def _sync_sql(sql, params=(), fetch="none"):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(SQLITE_MAX_RETRIES + 1):
        conn = sqlite3.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
        try:
            _configure_sync_connection(conn)
            # Synchronous compatibility calls share the same async DB loop.
            # This keeps the reusable compatibility connection alive between calls.
            if fetch == "one":
                return _run(fetch_one_sql(sql, params))
            if fetch == "all":
                return _run(fetch_all_sql(sql, params))
            return _run(execute(sql, params))
        except sqlite3.OperationalError as exc:
            last_error = exc
            if not _is_locked_error(exc) or attempt >= SQLITE_MAX_RETRIES:
                raise
            time.sleep(_retry_delay(attempt))
        finally:
            conn.close()
    raise last_error

async def fetch_all_sql(sql, params=()):
    db = await get_db()
    async with db.conn.execute(sql, tuple(params)) as cur:
        return [dict(r) for r in await cur.fetchall()]

async def fetch_one_sql(sql, params=()):
    rows = await fetch_all_sql(sql, params)
    return rows[0] if rows else None

def sync_all(table, where="", params=()):
    return _run(fetch_all(table, where, params))

def sync_one(table, where, params=()):
    return _run(fetch_one(table, where, params))

def sync_execute(sql, params=()):
    return _run(execute(sql, params))

def sync_execute_returning_one(sql, params=()):
    return _run(execute_returning_one(sql, params))

async def transaction(statements):
    db = await get_db()
    async with db.lock:
        await db.conn.execute("BEGIN IMMEDIATE")
        try:
            for sql, p in statements:
                await db.conn.execute(sql, tuple(p))
            await db.conn.commit()
        except Exception:
            await db.conn.rollback()
            raise

def sync_transaction(statements):
    return _run(transaction(statements))

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
    _configure_sync_connection(conn)
    return conn

async def shutdown_database():
    await close_all_dbs()

def _atexit_cleanup():
    try:
        shutdown_sync_loop()
    except Exception:
        logger.exception("database_sync_loop_shutdown_failed operation=atexit_cleanup")

atexit.register(_atexit_cleanup)
