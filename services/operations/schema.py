"""Generic operational-domain schema owned by TaskMG Core.

The schema models reusable capabilities rather than a healthcare vertical:
Workspace -> Reference Entity -> Case -> Workflow/Task/Follow-up -> Outcome.
Healthcare terminology is applied in services.healthcare, not here.
"""

from __future__ import annotations

TASK_COLUMNS = {
    "workspace_id": "TEXT REFERENCES workspaces(id)",
    "unit_id": "TEXT REFERENCES workspace_units(id)",
    "reference_id": "TEXT REFERENCES reference_entities(id)",
    "case_id": "TEXT REFERENCES cases(id)",
    "outcome_id": "TEXT REFERENCES outcomes(id)",
    "workflow_instance_id": "TEXT REFERENCES workflow_instances(id)",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
 id TEXT PRIMARY KEY,
 bot_key TEXT NOT NULL,
 name TEXT NOT NULL,
 workspace_type TEXT NOT NULL DEFAULT 'generic',
 timezone TEXT NOT NULL DEFAULT 'UTC',
 status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_workspaces_bot ON workspaces(bot_key,status);

CREATE TABLE IF NOT EXISTS workspace_units (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 name TEXT NOT NULL,
 unit_type TEXT NOT NULL DEFAULT 'branch',
 status TEXT NOT NULL DEFAULT 'active',
 UNIQUE(workspace_id,id)
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 user_id TEXT NOT NULL REFERENCES users(user_id),
 unit_id TEXT,
 role TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
 metadata_json TEXT NOT NULL DEFAULT '{}',
 FOREIGN KEY(workspace_id,unit_id) REFERENCES workspace_units(workspace_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_membership_scope
 ON workspace_memberships(workspace_id,user_id,COALESCE(unit_id,''));
CREATE INDEX IF NOT EXISTS idx_workspace_member_user
 ON workspace_memberships(user_id,workspace_id,status);

CREATE TABLE IF NOT EXISTS reference_entities (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL,
 unit_id TEXT NOT NULL,
 reference_type TEXT NOT NULL DEFAULT 'generic',
 external_reference TEXT,
 display_name TEXT NOT NULL,
 contact_value TEXT NOT NULL DEFAULT '',
 primary_owner_user_id TEXT REFERENCES users(user_id),
 status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(workspace_id,unit_id,id),
 UNIQUE(workspace_id,external_reference),
 FOREIGN KEY(workspace_id,unit_id) REFERENCES workspace_units(workspace_id,id)
);

CREATE TABLE IF NOT EXISTS cases (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL,
 unit_id TEXT NOT NULL,
 reference_id TEXT NOT NULL,
 case_type TEXT NOT NULL,
 title TEXT NOT NULL,
 owner_user_id TEXT NOT NULL REFERENCES users(user_id),
 primary_owner_user_id TEXT REFERENCES users(user_id),
 status TEXT NOT NULL DEFAULT 'active'
   CHECK(status IN ('active','waiting','blocked','completed','closed','cancelled')),
 current_stage TEXT NOT NULL DEFAULT '',
 blocker TEXT NOT NULL DEFAULT '',
 expected_at TEXT,
 external_reference TEXT NOT NULL DEFAULT '',
 next_action_task_id TEXT REFERENCES tasks(id),
 workflow_instance_id TEXT REFERENCES workflow_instances(id),
 opened_at TEXT NOT NULL,
 closed_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(workspace_id,unit_id,id),
 UNIQUE(workspace_id,unit_id,reference_id,id),
 FOREIGN KEY(workspace_id,unit_id,reference_id)
   REFERENCES reference_entities(workspace_id,unit_id,id)
);

CREATE TABLE IF NOT EXISTS outcomes (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 key TEXT NOT NULL,
 label TEXT NOT NULL,
 requires_next_action INTEGER NOT NULL CHECK(requires_next_action IN (0,1)),
 is_terminal INTEGER NOT NULL CHECK(is_terminal IN (0,1)),
 UNIQUE(workspace_id,key),
 UNIQUE(workspace_id,id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_workspace_identity
 ON tasks(workspace_id,unit_id,id);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace_case
 ON tasks(workspace_id,unit_id,case_id,status,deadline);

CREATE TABLE IF NOT EXISTS followups (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL,
 unit_id TEXT NOT NULL,
 reference_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 task_id TEXT NOT NULL UNIQUE,
 followup_type TEXT NOT NULL DEFAULT 'callback',
 owner_user_id TEXT NOT NULL REFERENCES users(user_id),
 due_at TEXT NOT NULL,
 attempt_number INTEGER NOT NULL DEFAULT 1 CHECK(attempt_number>=1),
 status TEXT NOT NULL DEFAULT 'due'
   CHECK(status IN ('due','in_progress','rescheduled','completed','closed')),
 outcome_id TEXT,
 next_followup_id TEXT REFERENCES followups(id),
 completed_at TEXT,
 created_at TEXT NOT NULL,
 UNIQUE(workspace_id,unit_id,id),
 FOREIGN KEY(workspace_id,unit_id,reference_id,case_id)
   REFERENCES cases(workspace_id,unit_id,reference_id,id),
 FOREIGN KEY(workspace_id,unit_id,task_id)
   REFERENCES tasks(workspace_id,unit_id,id),
 FOREIGN KEY(workspace_id,outcome_id)
   REFERENCES outcomes(workspace_id,id)
);
CREATE INDEX IF NOT EXISTS idx_followups_queue
 ON followups(workspace_id,unit_id,status,due_at,owner_user_id);
CREATE INDEX IF NOT EXISTS idx_cases_scope
 ON cases(workspace_id,unit_id,status,current_stage,primary_owner_user_id);

CREATE TABLE IF NOT EXISTS operational_audit (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 unit_id TEXT,
 actor_user_id TEXT NOT NULL,
 action TEXT NOT NULL,
 entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL,
 schema_version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 FOREIGN KEY(workspace_id,unit_id) REFERENCES workspace_units(workspace_id,id)
);
CREATE TRIGGER IF NOT EXISTS operational_audit_no_update
 BEFORE UPDATE ON operational_audit
 BEGIN SELECT RAISE(ABORT,'immutable_audit'); END;
CREATE TRIGGER IF NOT EXISTS operational_audit_no_delete
 BEFORE DELETE ON operational_audit
 BEGIN SELECT RAISE(ABORT,'immutable_audit'); END;

CREATE TABLE IF NOT EXISTS workflow_versions (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 template_key TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>=1),
 definition_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(workspace_id,template_key,version),
 UNIQUE(workspace_id,id)
);

CREATE TABLE IF NOT EXISTS workflow_instances (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL,
 unit_id TEXT NOT NULL,
 case_id TEXT NOT NULL UNIQUE,
 version_id TEXT NOT NULL,
 current_stage TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL,
 UNIQUE(workspace_id,unit_id,id),
 FOREIGN KEY(workspace_id,unit_id,case_id)
   REFERENCES cases(workspace_id,unit_id,id),
 FOREIGN KEY(workspace_id,version_id)
   REFERENCES workflow_versions(workspace_id,id)
);
CREATE TRIGGER IF NOT EXISTS workflow_version_no_update
 BEFORE UPDATE ON workflow_versions
 BEGIN SELECT RAISE(ABORT,'immutable_workflow_version'); END;
CREATE TRIGGER IF NOT EXISTS workflow_version_no_delete
 BEFORE DELETE ON workflow_versions
 BEGIN SELECT RAISE(ABORT,'immutable_workflow_version'); END;
"""

_TASK_TRIGGER_TEMPLATE = """
CREATE TRIGGER IF NOT EXISTS operational_task_scope_{operation_lower}
BEFORE {operation} ON tasks
BEGIN
 SELECT CASE WHEN NEW.workspace_id IS NULL AND
  (NEW.unit_id IS NOT NULL OR NEW.reference_id IS NOT NULL OR NEW.case_id IS NOT NULL
   OR NEW.outcome_id IS NOT NULL OR NEW.workflow_instance_id IS NOT NULL)
  THEN RAISE(ABORT,'invalid_workspace_scope') END;
 SELECT CASE WHEN NEW.workspace_id IS NOT NULL AND (
  NEW.unit_id IS NULL OR NEW.team_id IS NOT NULL OR
  NOT EXISTS (
    SELECT 1 FROM workspace_units u
    WHERE u.id=NEW.unit_id AND u.workspace_id=NEW.workspace_id
  ) OR
  (NEW.reference_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM reference_entities r
    WHERE r.id=NEW.reference_id AND r.workspace_id=NEW.workspace_id
      AND r.unit_id=NEW.unit_id
  )) OR
  (NEW.case_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM cases c
    WHERE c.id=NEW.case_id AND c.workspace_id=NEW.workspace_id
      AND c.unit_id=NEW.unit_id AND c.reference_id=NEW.reference_id
  )) OR
  (NEW.outcome_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM outcomes o
    WHERE o.id=NEW.outcome_id AND o.workspace_id=NEW.workspace_id
  )) OR
  (NEW.workflow_instance_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM workflow_instances w
    WHERE w.id=NEW.workflow_instance_id
      AND w.workspace_id=NEW.workspace_id
      AND w.unit_id=NEW.unit_id AND w.case_id=NEW.case_id
  )) OR
  NOT EXISTS (
    SELECT 1 FROM workspace_memberships m
    WHERE m.workspace_id=NEW.workspace_id AND m.user_id=NEW.user_id
      AND m.status='active' AND (m.unit_id IS NULL OR m.unit_id=NEW.unit_id)
  ) OR
  (NEW.assignee_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM workspace_memberships m
    WHERE m.workspace_id=NEW.workspace_id AND m.user_id=NEW.assignee_id
      AND (m.status='active' OR {unchanged_assignee})
      AND (m.unit_id IS NULL OR m.unit_id=NEW.unit_id)
  ))
 ) THEN RAISE(ABORT,'invalid_workspace_links') END;
END;

CREATE TRIGGER IF NOT EXISTS operational_case_next_action_{operation_lower}
BEFORE {operation} ON cases
WHEN NEW.next_action_task_id IS NOT NULL
BEGIN
 SELECT CASE WHEN NOT EXISTS (
  SELECT 1 FROM tasks t WHERE t.id=NEW.next_action_task_id
   AND t.workspace_id=NEW.workspace_id
   AND t.unit_id=NEW.unit_id
   AND t.case_id=NEW.id
   AND t.status IN ('pending','in_progress')
 ) THEN RAISE(ABORT,'invalid_next_action') END;
END;
"""

for _operation in ("INSERT", "UPDATE"):
    SCHEMA += (
        _TASK_TRIGGER_TEMPLATE
        .replace("{unchanged_assignee}", "NEW.assignee_id IS OLD.assignee_id" if _operation == "UPDATE" else "0")
        .replace("{operation_lower}", _operation.lower())
        .replace("{operation}", _operation)
    )

SCHEMA += """
CREATE TRIGGER IF NOT EXISTS operational_task_clear_next_action
AFTER UPDATE OF status ON tasks
WHEN NEW.status IN ('done','cancelled')
BEGIN
 UPDATE cases SET next_action_task_id=NULL WHERE next_action_task_id=NEW.id;
END;

CREATE TABLE IF NOT EXISTS operational_notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 workspace_id TEXT NOT NULL,
 unit_id TEXT NOT NULL,
 task_id TEXT NOT NULL,
 recipient_id TEXT NOT NULL REFERENCES users(user_id),
 kind TEXT NOT NULL CHECK(kind IN ('before_due','at_due','overdue')),
 send_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending'
   CHECK(status IN ('pending','sending','sent','cancelled','failed')),
 attempt INTEGER NOT NULL DEFAULT 0,
 sent_at TEXT,
 UNIQUE(task_id,kind,recipient_id),
 FOREIGN KEY(workspace_id,unit_id,task_id)
   REFERENCES tasks(workspace_id,unit_id,id)
);
CREATE INDEX IF NOT EXISTS idx_operational_notifications_pending
 ON operational_notifications(status,send_at);

CREATE TRIGGER IF NOT EXISTS operational_task_notifications_insert
AFTER INSERT ON tasks
WHEN NEW.workspace_id IS NOT NULL
 AND NEW.assignee_id IS NOT NULL
 AND NEW.deadline!=''
BEGIN
 INSERT INTO operational_notifications(
  workspace_id,unit_id,task_id,recipient_id,kind,send_at
 )
 SELECT NEW.workspace_id,NEW.unit_id,NEW.id,NEW.assignee_id,'before_due',
        strftime('%Y-%m-%dT%H:%M:%SZ',NEW.deadline,'-1 hour')
 WHERE strftime('%Y-%m-%dT%H:%M:%SZ',NEW.deadline,'-1 hour')>=NEW.created_at;
 INSERT INTO operational_notifications(
  workspace_id,unit_id,task_id,recipient_id,kind,send_at
 )
 SELECT NEW.workspace_id,NEW.unit_id,NEW.id,NEW.assignee_id,'at_due',NEW.deadline
 WHERE NEW.deadline>=NEW.created_at;
 INSERT INTO operational_notifications(
  workspace_id,unit_id,task_id,recipient_id,kind,send_at
 )
 VALUES(
  NEW.workspace_id,NEW.unit_id,NEW.id,NEW.assignee_id,'overdue',
  strftime('%Y-%m-%dT%H:%M:%SZ',NEW.deadline,'+1 day')
 );
END;

CREATE TRIGGER IF NOT EXISTS operational_task_notifications_cancel
AFTER UPDATE OF status ON tasks
WHEN NEW.status IN ('done','cancelled')
BEGIN
 UPDATE operational_notifications
 SET status='cancelled'
 WHERE task_id=NEW.id AND status='pending';
END;

CREATE TRIGGER IF NOT EXISTS operational_followup_task_requires_outcome
BEFORE UPDATE OF status ON tasks
WHEN NEW.workspace_id IS NOT NULL
 AND NEW.status='done'
 AND NEW.outcome_id IS NULL
 AND EXISTS(
  SELECT 1 FROM followups f
  WHERE f.task_id=NEW.id AND f.workspace_id=NEW.workspace_id
 )
BEGIN
 SELECT RAISE(ABORT,'followup_outcome_required');
END;
"""

LEGACY_TABLE_RENAMES = (
    ("clinic_organizations", "workspaces"),
    ("clinic_branches", "workspace_units"),
    ("clinic_memberships", "workspace_memberships"),
    ("patient_references", "reference_entities"),
    ("clinic_outcomes", "outcomes"),
    ("clinic_workflow_versions", "workflow_versions"),
    ("clinic_cases", "cases"),
    ("clinic_workflow_instances", "workflow_instances"),
    ("clinic_followups", "followups"),
    ("clinic_audit", "operational_audit"),
    ("clinic_notifications", "operational_notifications"),
)

GENERIC_METADATA_COLUMNS = {
    "workspaces": {
        "workspace_type": "TEXT NOT NULL DEFAULT 'generic'",
    },
    "workspace_units": {
        "unit_type": "TEXT NOT NULL DEFAULT 'branch'",
    },
    "workspace_memberships": {
        "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
    },
    "reference_entities": {
        "reference_type": "TEXT NOT NULL DEFAULT 'generic'",
    },
}

LEGACY_COLUMN_RENAMES = {
    "workspace_units": (("organization_id", "workspace_id"),),
    "workspace_memberships": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
    ),
    "reference_entities": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
        ("primary_doctor_user_id", "primary_owner_user_id"),
        ("phone", "contact_value"),
    ),
    "cases": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
        ("patient_id", "reference_id"),
        ("primary_doctor_user_id", "primary_owner_user_id"),
        ("appointment_reference", "external_reference"),
    ),
    "outcomes": (("organization_id", "workspace_id"),),
    "followups": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
        ("patient_id", "reference_id"),
    ),
    "operational_audit": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
    ),
    "workflow_versions": (("organization_id", "workspace_id"),),
    "workflow_instances": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
    ),
    "operational_notifications": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
    ),
    "tasks": (
        ("organization_id", "workspace_id"),
        ("branch_id", "unit_id"),
        ("patient_id", "reference_id"),
    ),
}

_LEGACY_TRIGGERS = (
    "clinic_audit_no_update",
    "clinic_audit_no_delete",
    "clinic_workflow_version_no_update",
    "clinic_workflow_version_no_delete",
    "clinic_task_scope_insert",
    "clinic_task_scope_update",
    "clinic_case_next_action_insert",
    "clinic_case_next_action_update",
    "clinic_task_clear_next_action",
    "clinic_task_notifications_insert",
    "clinic_task_notifications_cancel",
    "clinic_followup_task_requires_outcome",
)


async def _table_names(conn) -> set[str]:
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cursor:
        return {row[0] for row in await cursor.fetchall()}


async def _column_names(conn, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cursor:  # nosec B608
        return {row[1] for row in await cursor.fetchall()}


async def migrate(conn) -> None:
    """Migrate legacy clinic persistence to generic Core operations in-place."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        for trigger in _LEGACY_TRIGGERS:
            await conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")  # nosec B608

        tables = await _table_names(conn)
        for old, new in LEGACY_TABLE_RENAMES:
            if old in tables and new not in tables:
                await conn.execute(f"ALTER TABLE {old} RENAME TO {new}")  # nosec B608
                tables.remove(old)
                tables.add(new)

        tables = await _table_names(conn)
        for table, renames in LEGACY_COLUMN_RENAMES.items():
            if table not in tables:
                continue
            columns = await _column_names(conn, table)
            for old, new in renames:
                if old in columns and new not in columns:
                    await conn.execute(
                        f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}"  # nosec B608
                    )
                    columns.remove(old)
                    columns.add(new)

        for table, additions in GENERIC_METADATA_COLUMNS.items():
            if table not in tables:
                continue
            columns = await _column_names(conn, table)
            for name, definition in additions.items():
                if name not in columns:
                    await conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {definition}"  # nosec B608
                    )
                    columns.add(name)

        if "tasks" in tables:
            columns = await _column_names(conn, "tasks")
            for name, definition in TASK_COLUMNS.items():
                if name not in columns:
                    await conn.execute(
                        f"ALTER TABLE tasks ADD COLUMN {name} {definition}"  # nosec B608
                    )

        await conn.commit()
    except BaseException:
        await conn.rollback()
        raise

    await conn.executescript(SCHEMA)

    # Legacy rows did not carry generic type metadata. Preserve them as the
    # Healthcare vertical while keeping the Core schema vertical-neutral.
    await conn.execute(
        "UPDATE workspaces SET workspace_type='healthcare' "
        "WHERE workspace_type='generic'"
    )
    await conn.execute(
        "UPDATE reference_entities SET reference_type='patient' "
        "WHERE reference_type='generic'"
    )
    await conn.commit()
