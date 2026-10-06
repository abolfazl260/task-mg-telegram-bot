"""CSV import/export for typed Clinic items with one validation contract."""
from __future__ import annotations

import csv
import io
from services.database import fetch_one_sql, fetch_all_sql, execute
from services import clinic_typed, task_attribute_service as attributes, contact_point_service

CONTACT_COLUMNS = {'phone': 'phone', 'phone_home': 'phone', 'phone_work': 'phone', 'phone_emergency': 'phone', 'email': 'email', 'address': 'address'}


def _rows(csv_text):
    if not isinstance(csv_text, str) or len(csv_text.encode()) > 5 * 1024 * 1024:
        raise ValueError('invalid_csv')
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or 'display_name' not in reader.fieldnames:
        raise ValueError('display_name_column_required')
    return list(reader), [str(x) for x in reader.fieldnames]


async def preview_async(scope, csv_text: str, *, branch_id: str | None = None):
    rows, fields = _rows(csv_text); errors=[]; valid=[]; seen=set()
    for index, row in enumerate(rows, 2):
        name = (row.get('display_name') or '').strip(); identity=(row.get('patient_id') or row.get('external_id') or '').strip()
        row_errors=[]
        if not name: row_errors.append('display_name_required')
        if identity in seen and identity: row_errors.append('duplicate_identity_in_file')
        if identity: seen.add(identity)
        if row.get('date_of_birth'):
            try: __import__('datetime').date.fromisoformat(row['date_of_birth'])
            except ValueError: row_errors.append('invalid_date_of_birth')
        if row_errors: errors.append({'row': index, 'errors': row_errors})
        else: valid.append({'row': index, 'identity': identity, 'display_name': name})
    return {'total': len(rows), 'valid': len(valid), 'invalid': len(errors), 'fields': fields, 'rows': valid, 'errors': errors}


async def import_async(scope, csv_text: str, *, branch_id: str, confirmed: bool = False):
    preview = await preview_async(scope, csv_text, branch_id=branch_id)
    if not confirmed: return {'confirmed': False, 'preview': preview}
    if preview['invalid']: raise ValueError('confirm_requires_valid_rows')
    rows, _fields = _rows(csv_text); created=[]; duplicates=[]; errors=[]
    try:
        for index, row in enumerate(rows, 2):
            identity=(row.get('patient_id') or row.get('external_id') or '').strip()
            existing = await fetch_one_sql("SELECT id FROM tasks WHERE workspace_id=? AND unit_id=? AND work_item_type='patient' AND reference_id=? AND archived_at IS NULL", (scope.workspace_id, branch_id, identity)) if identity else None
            if existing:
                duplicates.append({'row': index, 'task_id': existing['id']}); continue
            patient = await clinic_typed.create_patient_async(scope, branch_id, row['display_name'], doctor_id=row.get('doctor_id') or None, reference_id=identity or None)
            created.append(patient['id'])
            for column, ctype in CONTACT_COLUMNS.items():
                value=(row.get(column) or '').strip()
                if value: await contact_point_service.create_contact_point_async(patient['id'], ctype, value, str(scope.actor_id), label=column.removeprefix('phone_'))
            for key, value in row.items():
                if key in {'display_name','patient_id','external_id','doctor_id',*CONTACT_COLUMNS} or not value: continue
                definition = await fetch_one_sql("SELECT id FROM task_attribute_definitions WHERE workspace_id=? AND work_item_type='patient' AND field_key=? AND active=1 ORDER BY version DESC LIMIT 1", (scope.workspace_id, key))
                if not definition: continue
                await attributes.set_task_attribute_async(patient['id'], key, value, str(scope.actor_id), definition_id=definition['id'])
    except Exception:
        for task_id in created: await execute("UPDATE tasks SET archived_at=datetime('now') WHERE id=?", (task_id,))
        raise
    return {'confirmed': True, 'created': len(created), 'duplicates': duplicates, 'errors': errors}


async def export_async(scope, actor_id: str, *, branch_id: str | None = None, include_sessions: bool = True):
    clauses=['t.workspace_id=?','t.work_item_type=\'patient\'','t.archived_at IS NULL']; params=[scope.workspace_id]
    if branch_id: clauses.append('t.unit_id=?'); params.append(branch_id)
    rows=await fetch_all_sql('SELECT t.* FROM tasks t WHERE '+' AND '.join(clauses)+' ORDER BY t.created_at,t.id',tuple(params))
    out=io.StringIO(); writer=csv.DictWriter(out, fieldnames=['patient_id','display_name','branch_id','status','created_at','sessions','followups']); writer.writeheader()
    for row in rows:
        try: await __import__('services.work_item_access',fromlist=['authorized_task']).authorized_task(row['id'], actor_id)
        except PermissionError: continue
        children=await fetch_all_sql("SELECT work_item_type,status FROM tasks WHERE parent_task_id=? AND archived_at IS NULL",(row['id'],)) if include_sessions else []
        writer.writerow({'patient_id': row['reference_id'] or row['id'], 'display_name': row['title'], 'branch_id': row['unit_id'], 'status': row['status'], 'created_at': row['created_at'], 'sessions': sum(1 for x in children if x['work_item_type']=='session'), 'followups': sum(1 for x in children if x['work_item_type']=='followup')})
    return {'filename':'clinic-patients.csv','content':out.getvalue(),'content_type':'text/csv; charset=utf-8'}
