"""Additive Healthcare schema; legacy tasks remain unscoped and unchanged."""

TASK_COLUMNS = {
    "organization_id": "TEXT REFERENCES clinic_organizations(id)",
    "branch_id": "TEXT REFERENCES clinic_branches(id)",
    "patient_id": "TEXT REFERENCES patient_references(id)",
    "case_id": "TEXT REFERENCES clinic_cases(id)",
    "outcome_id": "TEXT REFERENCES clinic_outcomes(id)",
    "workflow_instance_id": "TEXT REFERENCES clinic_workflow_instances(id)",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS clinic_organizations (
 id TEXT PRIMARY KEY, bot_key TEXT NOT NULL, name TEXT NOT NULL,
 timezone TEXT NOT NULL DEFAULT 'Asia/Tehran', status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS clinic_branches (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES clinic_organizations(id),
 name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', UNIQUE(organization_id,id)
);
CREATE TABLE IF NOT EXISTS clinic_memberships (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES clinic_organizations(id),
 user_id TEXT NOT NULL REFERENCES users(user_id), branch_id TEXT,
 role TEXT NOT NULL CHECK(role IN ('owner','manager','doctor','dentist','reception','coordinator','assistant','admin')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
 CHECK(branch_id IS NOT NULL OR role IN ('owner','manager','admin')),
 FOREIGN KEY(organization_id,branch_id) REFERENCES clinic_branches(organization_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clinic_membership_scope
 ON clinic_memberships(organization_id,user_id,COALESCE(branch_id,''));
CREATE INDEX IF NOT EXISTS idx_clinic_member_user ON clinic_memberships(user_id,organization_id,status);
CREATE TABLE IF NOT EXISTS patient_references (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, branch_id TEXT NOT NULL,
 external_reference TEXT, display_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
 primary_doctor_user_id TEXT REFERENCES users(user_id), status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(organization_id,branch_id,id), UNIQUE(organization_id,external_reference),
 FOREIGN KEY(organization_id,branch_id) REFERENCES clinic_branches(organization_id,id)
);
CREATE TABLE IF NOT EXISTS clinic_cases (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, branch_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 case_type TEXT NOT NULL, title TEXT NOT NULL, owner_user_id TEXT NOT NULL REFERENCES users(user_id),
 primary_doctor_user_id TEXT REFERENCES users(user_id),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','waiting','blocked','completed','closed','cancelled')),
 current_stage TEXT NOT NULL DEFAULT '', blocker TEXT NOT NULL DEFAULT '', expected_at TEXT,
 appointment_reference TEXT NOT NULL DEFAULT '', next_action_task_id TEXT REFERENCES tasks(id),
 workflow_instance_id TEXT REFERENCES clinic_workflow_instances(id),
 opened_at TEXT NOT NULL, closed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(organization_id,branch_id,id), UNIQUE(organization_id,branch_id,patient_id,id),
 FOREIGN KEY(organization_id,branch_id,patient_id) REFERENCES patient_references(organization_id,branch_id,id)
);
CREATE TABLE IF NOT EXISTS clinic_outcomes (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES clinic_organizations(id),
 key TEXT NOT NULL, label TEXT NOT NULL, requires_next_action INTEGER NOT NULL CHECK(requires_next_action IN (0,1)),
 is_terminal INTEGER NOT NULL CHECK(is_terminal IN (0,1)), UNIQUE(organization_id,key), UNIQUE(organization_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_clinic_identity ON tasks(organization_id,branch_id,id);
CREATE INDEX IF NOT EXISTS idx_tasks_clinic_case ON tasks(organization_id,branch_id,case_id,status,deadline);
CREATE TABLE IF NOT EXISTS clinic_followups (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, branch_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 case_id TEXT NOT NULL, task_id TEXT NOT NULL UNIQUE, followup_type TEXT NOT NULL DEFAULT 'callback',
 owner_user_id TEXT NOT NULL REFERENCES users(user_id), due_at TEXT NOT NULL,
 attempt_number INTEGER NOT NULL DEFAULT 1 CHECK(attempt_number>=1),
 status TEXT NOT NULL DEFAULT 'due' CHECK(status IN ('due','in_progress','rescheduled','completed','closed')),
 outcome_id TEXT, next_followup_id TEXT REFERENCES clinic_followups(id), completed_at TEXT, created_at TEXT NOT NULL,
 UNIQUE(organization_id,branch_id,id),
 FOREIGN KEY(organization_id,branch_id,patient_id,case_id) REFERENCES clinic_cases(organization_id,branch_id,patient_id,id),
 FOREIGN KEY(organization_id,branch_id,task_id) REFERENCES tasks(organization_id,branch_id,id),
 FOREIGN KEY(organization_id,outcome_id) REFERENCES clinic_outcomes(organization_id,id)
);
CREATE INDEX IF NOT EXISTS idx_followups_queue ON clinic_followups(organization_id,branch_id,status,due_at,owner_user_id);
CREATE INDEX IF NOT EXISTS idx_cases_scope ON clinic_cases(organization_id,branch_id,status,current_stage,primary_doctor_user_id);
CREATE TABLE IF NOT EXISTS clinic_audit (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES clinic_organizations(id), branch_id TEXT,
 actor_user_id TEXT NOT NULL, action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 schema_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 FOREIGN KEY(organization_id,branch_id) REFERENCES clinic_branches(organization_id,id)
);
CREATE TRIGGER IF NOT EXISTS clinic_audit_no_update BEFORE UPDATE ON clinic_audit
 BEGIN SELECT RAISE(ABORT,'immutable_audit'); END;
CREATE TRIGGER IF NOT EXISTS clinic_audit_no_delete BEFORE DELETE ON clinic_audit
 BEGIN SELECT RAISE(ABORT,'immutable_audit'); END;
CREATE TABLE IF NOT EXISTS clinic_workflow_versions (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES clinic_organizations(id),
 template_key TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>=1), definition_json TEXT NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(organization_id,template_key,version), UNIQUE(organization_id,id)
);
CREATE TABLE IF NOT EXISTS clinic_workflow_instances (
 id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, branch_id TEXT NOT NULL, case_id TEXT NOT NULL UNIQUE,
 version_id TEXT NOT NULL, current_stage TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL,
 UNIQUE(organization_id,branch_id,id),
 FOREIGN KEY(organization_id,branch_id,case_id) REFERENCES clinic_cases(organization_id,branch_id,id),
 FOREIGN KEY(organization_id,version_id) REFERENCES clinic_workflow_versions(organization_id,id)
);
CREATE TRIGGER IF NOT EXISTS clinic_workflow_version_no_update BEFORE UPDATE ON clinic_workflow_versions
 BEGIN SELECT RAISE(ABORT,'immutable_workflow_version'); END;
CREATE TRIGGER IF NOT EXISTS clinic_workflow_version_no_delete BEFORE DELETE ON clinic_workflow_versions
 BEGIN SELECT RAISE(ABORT,'immutable_workflow_version'); END;
"""

# Validate task links even when a caller bypasses the domain service. Both insert
# and update are protected, including moving a task or changing its case/patient.
TASK_TRIGGER_TEMPLATE = """
CREATE TRIGGER IF NOT EXISTS clinic_task_scope_{operation.lower()} BEFORE {operation} ON tasks
BEGIN
 SELECT CASE WHEN NEW.organization_id IS NULL AND
  (NEW.branch_id IS NOT NULL OR NEW.patient_id IS NOT NULL OR NEW.case_id IS NOT NULL OR NEW.outcome_id IS NOT NULL OR NEW.workflow_instance_id IS NOT NULL)
  THEN RAISE(ABORT,'invalid_clinic_scope') END;
 SELECT CASE WHEN NEW.organization_id IS NOT NULL AND (
  NEW.branch_id IS NULL OR NEW.team_id IS NOT NULL OR
  NOT EXISTS (SELECT 1 FROM clinic_branches b WHERE b.id=NEW.branch_id AND b.organization_id=NEW.organization_id) OR
  (NEW.patient_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM patient_references p WHERE p.id=NEW.patient_id AND p.organization_id=NEW.organization_id AND p.branch_id=NEW.branch_id)) OR
  (NEW.case_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM clinic_cases c WHERE c.id=NEW.case_id AND c.organization_id=NEW.organization_id AND c.branch_id=NEW.branch_id AND c.patient_id=NEW.patient_id)) OR
  (NEW.outcome_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM clinic_outcomes o WHERE o.id=NEW.outcome_id AND o.organization_id=NEW.organization_id)) OR
  (NEW.workflow_instance_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM clinic_workflow_instances w WHERE w.id=NEW.workflow_instance_id AND w.organization_id=NEW.organization_id AND w.branch_id=NEW.branch_id AND w.case_id=NEW.case_id)) OR
  NOT EXISTS (SELECT 1 FROM clinic_memberships m WHERE m.organization_id=NEW.organization_id AND m.user_id=NEW.user_id AND (m.branch_id IS NULL OR m.branch_id=NEW.branch_id)) OR
  (NEW.assignee_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM clinic_memberships m WHERE m.organization_id=NEW.organization_id AND m.user_id=NEW.assignee_id AND (m.status='active' OR {unchanged_assignee}) AND (m.branch_id IS NULL OR m.branch_id=NEW.branch_id)))
 ) THEN RAISE(ABORT,'invalid_clinic_links') END;
END;
CREATE TRIGGER IF NOT EXISTS clinic_case_next_action_{operation.lower()} BEFORE {operation} ON clinic_cases
WHEN NEW.next_action_task_id IS NOT NULL
BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM tasks t WHERE t.id=NEW.next_action_task_id
  AND t.organization_id=NEW.organization_id AND t.branch_id=NEW.branch_id AND t.case_id=NEW.id
  AND t.status IN ('pending','in_progress')) THEN RAISE(ABORT,'invalid_next_action') END;
END;
"""
for operation in ("INSERT", "UPDATE"):
    SCHEMA += (TASK_TRIGGER_TEMPLATE
        .replace("{unchanged_assignee}", "NEW.assignee_id IS OLD.assignee_id" if operation == "UPDATE" else "0")
        .replace("{operation.lower()}", operation.lower())
        .replace("{operation}", operation))
SCHEMA += """
CREATE TRIGGER IF NOT EXISTS clinic_task_clear_next_action AFTER UPDATE OF status ON tasks
WHEN NEW.status IN ('done','cancelled')
BEGIN
 UPDATE clinic_cases SET next_action_task_id=NULL WHERE next_action_task_id=NEW.id;
END;
"""

SCHEMA += """
CREATE TABLE IF NOT EXISTS clinic_notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id TEXT NOT NULL,
 branch_id TEXT NOT NULL, task_id TEXT NOT NULL, recipient_id TEXT NOT NULL REFERENCES users(user_id),
 kind TEXT NOT NULL CHECK(kind IN ('before_due','at_due','overdue')),
 send_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','sending','sent','cancelled','failed')),
 attempt INTEGER NOT NULL DEFAULT 0, sent_at TEXT,
 UNIQUE(task_id,kind,recipient_id),
 FOREIGN KEY(organization_id,branch_id,task_id) REFERENCES tasks(organization_id,branch_id,id)
);
CREATE INDEX IF NOT EXISTS idx_clinic_notifications_pending ON clinic_notifications(status,send_at);
CREATE TRIGGER IF NOT EXISTS clinic_task_notifications_insert AFTER INSERT ON tasks
WHEN NEW.organization_id IS NOT NULL AND NEW.assignee_id IS NOT NULL AND NEW.deadline!=''
BEGIN
 INSERT INTO clinic_notifications(organization_id,branch_id,task_id,recipient_id,kind,send_at)
 SELECT NEW.organization_id,NEW.branch_id,NEW.id,NEW.assignee_id,'before_due',strftime('%Y-%m-%dT%H:%M:%SZ',NEW.deadline,'-1 hour')
 WHERE strftime('%Y-%m-%dT%H:%M:%SZ',NEW.deadline,'-1 hour')>=NEW.created_at;
 INSERT INTO clinic_notifications(organization_id,branch_id,task_id,recipient_id,kind,send_at)
 SELECT NEW.organization_id,NEW.branch_id,NEW.id,NEW.assignee_id,'at_due',NEW.deadline WHERE NEW.deadline>=NEW.created_at;
 INSERT INTO clinic_notifications(organization_id,branch_id,task_id,recipient_id,kind,send_at)
 VALUES(NEW.organization_id,NEW.branch_id,NEW.id,NEW.assignee_id,'overdue',strftime('%Y-%m-%dT%H:%M:%SZ',NEW.deadline,'+1 day'));
END;
CREATE TRIGGER IF NOT EXISTS clinic_task_notifications_cancel AFTER UPDATE OF status ON tasks
WHEN NEW.status IN ('done','cancelled')
BEGIN
 UPDATE clinic_notifications SET status='cancelled' WHERE task_id=NEW.id AND status='pending';
END;
"""

SCHEMA += """
CREATE TRIGGER IF NOT EXISTS clinic_followup_task_requires_outcome BEFORE UPDATE OF status ON tasks
WHEN NEW.organization_id IS NOT NULL AND NEW.status='done' AND NEW.outcome_id IS NULL
 AND EXISTS(SELECT 1 FROM clinic_followups f WHERE f.task_id=NEW.id AND f.organization_id=NEW.organization_id)
BEGIN SELECT RAISE(ABORT,'followup_outcome_required'); END;
"""
