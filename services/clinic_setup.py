"""Idempotent standalone Clinic workspace bootstrap."""
from __future__ import annotations

import uuid

from services.database import execute, fetch_all_sql, fetch_one_sql, transaction
from services.healthcare.service import HEALTHCARE_CONFIG
from services.operations.service import create_workspace, now

DEFAULT_FIELDS = {
    'patient': [
        ('patient_id', 'شناسه بیمار', 'text', False), ('first_name', 'نام', 'text', True),
        ('last_name', 'نام خانوادگی', 'text', True), ('display_name', 'نام نمایشی', 'text', False),
        ('date_of_birth', 'تاریخ تولد', 'date', False), ('gender', 'جنسیت', 'select', False),
        ('disease_history', 'سابقه بیماری', 'long_text', False), ('chronic_conditions', 'بیماری زمینه‌ای', 'long_text', False),
        ('allergies', 'حساسیت‌ها', 'long_text', False), ('medications', 'داروها', 'long_text', False),
        ('diagnoses', 'تشخیص‌ها', 'long_text', False), ('clinical_notes', 'یادداشت بالینی', 'long_text', False),
        ('treatment_information', 'اطلاعات درمان', 'long_text', False), ('status', 'وضعیت', 'select', False),
    ],
    'session': [
        ('scheduled_at', 'زمان ویزیت', 'datetime', True), ('actual_started_at', 'شروع واقعی', 'datetime', False),
        ('actual_ended_at', 'پایان واقعی', 'datetime', False), ('doctor', 'پزشک', 'user_reference', False),
        ('session_type', 'نوع ویزیت', 'select', False), ('reason', 'علت مراجعه', 'long_text', False),
        ('session_notes', 'یادداشت ویزیت', 'long_text', False), ('clinical_notes', 'یادداشت بالینی', 'long_text', False),
        ('next_followup_at', 'پیگیری بعدی', 'datetime', False), ('status', 'وضعیت', 'select', False),
    ],
    'followup': [
        ('due_at', 'موعد پیگیری', 'datetime', True), ('owner', 'مسئول', 'user_reference', False),
        ('outcome', 'نتیجه', 'select', False), ('next_action', 'اقدام بعدی', 'long_text', False), ('status', 'وضعیت', 'select', False),
    ],
}

async def _ensure_definitions(workspace_id, bot_key, configured=None):
    configured = configured or {}
    made = 0
    for item_type, fields in DEFAULT_FIELDS.items():
        for key, label, dtype, required in fields:
            if configured.get(item_type, {}).get(key, {}).get('enabled') is False:
                continue
            exists = await fetch_one_sql("SELECT id FROM task_attribute_definitions WHERE bot_key=? AND workspace_id=? AND work_item_type=? AND field_key=? AND active=1", (bot_key, workspace_id, item_type, key))
            if exists: continue
            await execute("INSERT INTO task_attribute_definitions(id,bot_key,workspace_id,work_item_type,field_key,label,data_type,required,repeatable,validation_json,active,version,created_at,updated_at,sensitive,view_roles_json,edit_roles_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, bot_key, workspace_id, item_type, key, label, dtype, int(required), 0, '{}', 1, 1, now(), now(), int(key in {'diagnoses','clinical_notes','allergies','medications'}), '["owner","admin","manager","doctor","dentist"]', '["owner","admin","doctor","dentist"]'))
            made += 1
    return made

async def bootstrap_async(actor_id: str, bot_key: str, name: str, *, timezone_name='Asia/Tehran', branches=None, staff=None, field_config=None):
    existing = await fetch_one_sql("SELECT w.id FROM workspaces w JOIN workspace_memberships m ON m.workspace_id=w.id AND m.user_id=? WHERE w.bot_key=? AND w.workspace_type='healthcare' AND w.name=? AND w.status='active' LIMIT 1", (str(actor_id), bot_key, str(name).strip()))
    workspace_id = existing['id'] if existing else await create_workspace(actor_id, bot_key, name, config=HEALTHCARE_CONFIG, timezone_name=timezone_name)
    _owner = await fetch_one_sql("SELECT * FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active' LIMIT 1", (workspace_id, str(actor_id)))
    branch_map = {row['name']: row['id'] for row in await fetch_all_sql('SELECT id,name FROM workspace_units WHERE workspace_id=? AND status=\'active\'', (workspace_id,))}
    for branch in branches or []:
        branch_name = str(branch.get('name') if isinstance(branch, dict) else branch).strip()
        if not branch_name: continue
        branch_map.setdefault(branch_name, uuid.uuid4().hex)
        if not await fetch_one_sql('SELECT id FROM workspace_units WHERE workspace_id=? AND name=?', (workspace_id, branch_name)):
            await execute('INSERT INTO workspace_units(id,workspace_id,name,unit_type) VALUES(?,?,?,\'branch\')', (branch_map[branch_name], workspace_id, branch_name))
    for member in staff or []:
        if not isinstance(member, dict) or not member.get('user_id'): continue
        branch_id = member.get('branch_id')
        if not branch_id and member.get('branch_name'): branch_id = branch_map.get(member['branch_name'])
        existing_member = await fetch_one_sql('SELECT id FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND unit_id IS ?', (workspace_id, str(member['user_id']), branch_id))
        await transaction([
            ('INSERT OR IGNORE INTO users(user_id) VALUES(?)', (str(member['user_id']),)),
            ('INSERT INTO workspace_memberships(id,workspace_id,user_id,unit_id,role,status) VALUES(?,?,?,?,?,\'active\') ON CONFLICT(id) DO UPDATE SET role=excluded.role,status=excluded.status', (existing_member['id'] if existing_member else uuid.uuid4().hex, workspace_id, str(member['user_id']), branch_id, member.get('role', 'reception'))),
        ])
    definitions_created = await _ensure_definitions(workspace_id, bot_key, field_config)
    status = await setup_status_async(workspace_id, actor_id)
    return {**status, 'definitions_created': definitions_created}

async def setup_status_async(workspace_id: str, actor_id: str):
    member = await fetch_one_sql("SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active'", (workspace_id, str(actor_id)))
    if not member: raise PermissionError('setup_permission_denied')
    workspace = await fetch_one_sql('SELECT * FROM workspaces WHERE id=? AND workspace_type=\'healthcare\' AND status=\'active\'', (workspace_id,))
    if not workspace: raise ValueError('clinic_not_found')
    branches = await fetch_one_sql('SELECT COUNT(*) AS n FROM workspace_units WHERE workspace_id=? AND status=\'active\'', (workspace_id,))
    staff = await fetch_one_sql('SELECT COUNT(DISTINCT user_id) AS n FROM workspace_memberships WHERE workspace_id=? AND status=\'active\'', (workspace_id,))
    schemas = await fetch_one_sql('SELECT COUNT(*) AS n FROM task_attribute_definitions WHERE workspace_id=? AND active=1', (workspace_id,))
    return {'workspace_id': workspace_id, 'name': workspace['name'], 'timezone': workspace['timezone'], 'branches': int(branches['n']), 'staff': int(staff['n']), 'attribute_definitions': int(schemas['n']), 'ready': bool(branches['n'] and staff['n'] and schemas['n'])}

bootstrap = bootstrap_async
