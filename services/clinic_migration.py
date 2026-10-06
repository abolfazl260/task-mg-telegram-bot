"""Repeatable legacy Healthcare -> typed Patient/child migration.

The migration is intentionally explicit about backups. It creates stable mapping
rows, never mutates generic TaskBot rows, and can archive only rows it created.
"""
from __future__ import annotations

import json
import uuid

from services.database import execute, fetch_all_sql, fetch_one_sql
from services.healthcare.access import ClinicAccessError, Scope
from services.operations.service import now

CLINICAL_FIELDS = {
    "allergies": "long_text", "chronic_conditions": "long_text", "medications": "long_text",
    "diagnoses": "long_text", "clinical_notes": "long_text",
}


def _stable(kind, legacy_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"taskmg:clinic:{kind}:{legacy_id}"))


def _json(value):
    return json.dumps(value if isinstance(value, (dict, list)) else {}, ensure_ascii=False, separators=(",", ":"))


async def _definition(workspace_id, bot_key, item_type, field_key, data_type):
    row = await fetch_one_sql("SELECT * FROM task_attribute_definitions WHERE bot_key=? AND workspace_id=? AND work_item_type=? AND field_key=? AND active=1 ORDER BY version DESC LIMIT 1", (bot_key, workspace_id, item_type, field_key))
    if row:
        return row
    definition_id = _stable(f"definition:{workspace_id}:{item_type}", field_key)
    await execute("""INSERT OR IGNORE INTO task_attribute_definitions(id,bot_key,workspace_id,work_item_type,field_key,label,data_type,version,active,created_at,updated_at,sensitive,view_roles_json,edit_roles_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (definition_id, bot_key, workspace_id, item_type, field_key, field_key.replace('_', ' ').title(), data_type, 1, 1, now(), now(), 1 if field_key in {'diagnoses','clinical_notes'} else 0, '["owner","admin","manager","doctor","dentist"]', '["owner","admin","manager","doctor","dentist"]'))
    return await fetch_one_sql("SELECT * FROM task_attribute_definitions WHERE id=?", (definition_id,))


async def migrate_workspace_async(scope: Scope, *, backup_reference: str, backup_confirmed: bool = False) -> dict:
    if not backup_confirmed or not str(backup_reference or '').strip():
        raise ValueError('backup_required')
    await scope.predicate('memberships.manage')
    workspace = await fetch_one_sql('SELECT * FROM workspaces WHERE id=? AND status=\'active\'', (scope.workspace_id,))
    if not workspace:
        raise ClinicAccessError('forbidden')
    run_id = str(uuid.uuid4())
    await execute("INSERT INTO typed_migration_runs(id,workspace_id,status,backup_reference,created_by,created_at) VALUES(?,?,?,?,?,?)", (run_id, scope.workspace_id, 'running', str(backup_reference), str(scope.actor_id), now()))
    created = {'patients': 0, 'children': 0, 'attributes': 0, 'run_id': run_id}
    try:
        patients = await fetch_all_sql('SELECT * FROM reference_entities WHERE workspace_id=? AND reference_type=\'patient\' ORDER BY id', (scope.workspace_id,))
        for patient in patients:
            existing = await fetch_one_sql("SELECT * FROM tasks WHERE workspace_id=? AND reference_id=? AND work_item_type='patient' LIMIT 1", (scope.workspace_id, patient['id']))
            typed_id = existing['id'] if existing else _stable('patient', patient['id'])
            if not existing:
                await execute("INSERT INTO tasks(id,bot_key,work_item_type,user_id,title,status,created_at,workspace_id,unit_id,reference_id,assignee_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (typed_id, workspace['bot_key'], 'patient', str(scope.actor_id), patient['display_name'], 'pending', patient.get('created_at') or now(), scope.workspace_id, patient['unit_id'], patient['id'], patient.get('primary_owner_user_id')))
                await execute("INSERT INTO typed_work_item_data(task_id,data_json,created_at,updated_at) VALUES(?,?,?,?)", (typed_id, _json({'legacy_reference_id': patient['id'], 'phone': patient.get('contact_value', ''), 'status': patient.get('status', 'active')}), now(), now()))
                created['patients'] += 1
            await execute("INSERT OR IGNORE INTO typed_migration_map(run_id,workspace_id,legacy_kind,legacy_id,typed_task_id) VALUES(?,?,?,?,?)", (run_id, scope.workspace_id, 'patient', patient['id'], typed_id))
            record = await fetch_one_sql('SELECT * FROM clinical_records WHERE workspace_id=? AND patient_id=?', (scope.workspace_id, patient['id']))
            if record:
                for field, dtype in CLINICAL_FIELDS.items():
                    value = record.get(field)
                    if value in (None, ''): continue
                    definition = await _definition(scope.workspace_id, workspace['bot_key'], 'patient', field, dtype)
                    value_id = _stable(f'value:{typed_id}:{definition["id"]}', '0')
                    await execute("""INSERT INTO task_attribute_values(id,task_id,definition_id,definition_version,ordinal,value_text,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(task_id,definition_id,ordinal) DO UPDATE SET value_text=excluded.value_text,updated_at=excluded.updated_at""", (value_id, typed_id, definition['id'], definition.get('version', 1), 0, str(value), now(), now()))
                    created['attributes'] += 1
        followups = await fetch_all_sql('SELECT * FROM followups WHERE workspace_id=? ORDER BY id', (scope.workspace_id,))
        for followup in followups:
            mapping = await fetch_one_sql("SELECT typed_task_id FROM typed_migration_map WHERE workspace_id=? AND legacy_kind='followup' AND legacy_id=?", (scope.workspace_id, followup['id']))
            if mapping:
                continue
            parent = await fetch_one_sql("SELECT typed_task_id FROM typed_migration_map WHERE workspace_id=? AND legacy_kind='patient' AND legacy_id=?", (scope.workspace_id, followup['reference_id']))
            if not parent:
                continue
            typed_id = _stable('followup', followup['id'])
            await execute("INSERT OR IGNORE INTO tasks(id,bot_key,work_item_type,parent_task_id,user_id,title,status,deadline,created_at,workspace_id,unit_id,reference_id,assignee_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (typed_id, workspace['bot_key'], 'followup', str(scope.actor_id), 'Legacy follow-up', followup.get('status', 'due'), followup.get('due_at', ''), followup.get('created_at') or now(), scope.workspace_id, followup['unit_id'], followup['reference_id'], followup.get('owner_user_id')))
            await execute("INSERT OR IGNORE INTO typed_work_item_data(task_id,data_json,created_at,updated_at) VALUES(?,?,?,?)", (typed_id, _json({'legacy_followup_id': followup['id'], 'attempt_number': followup.get('attempt_number', 1), 'status': followup.get('status', 'due')}), now(), now()))
            await execute("INSERT INTO typed_migration_map(run_id,workspace_id,legacy_kind,legacy_id,typed_task_id) VALUES(?,?,?,?,?)", (run_id, scope.workspace_id, 'followup', followup['id'], typed_id))
            created['children'] += 1
        await execute("UPDATE typed_migration_runs SET status='completed',completed_at=? WHERE id=?", (now(), run_id))
        return {**created, 'status': 'completed', 'backup_reference': backup_reference}
    except Exception:
        await execute("UPDATE typed_migration_runs SET status='failed',completed_at=? WHERE id=?", (now(), run_id))
        raise


async def rollback_run_async(scope: Scope, run_id: str) -> dict:
    run = await fetch_one_sql("SELECT * FROM typed_migration_runs WHERE id=? AND workspace_id=?", (str(run_id), scope.workspace_id))
    if not run or run['status'] not in {'completed', 'failed'}:
        raise ValueError('migration_run_not_found')
    await scope.predicate('memberships.manage')
    maps = await fetch_all_sql('SELECT typed_task_id FROM typed_migration_map WHERE run_id=?', (str(run_id),))
    for row in maps:
        await execute("UPDATE tasks SET archived_at=? WHERE id=? AND workspace_id=?", (now(), row['typed_task_id'], scope.workspace_id))
    await execute("UPDATE typed_migration_runs SET status='rolled_back',completed_at=? WHERE id=?", (now(), str(run_id)))
    return {'run_id': run_id, 'status': 'rolled_back', 'archived_items': len(maps)}


def _run(coro):
    from services.database import _run as db_run
    return db_run(coro)

migrate_workspace = lambda *a, **k: _run(migrate_workspace_async(*a, **k))
rollback_run = lambda *a, **k: _run(rollback_run_async(*a, **k))
