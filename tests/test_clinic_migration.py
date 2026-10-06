import pytest

from services import clinic_migration
from services.database import fetch_all_sql, fetch_one_sql


@pytest.mark.asyncio
async def test_legacy_clinic_migration_is_repeatable_and_rollback_archives(clinic):
    scope = clinic['owner']
    record = await fetch_one_sql('SELECT id FROM clinical_records WHERE workspace_id=? AND patient_id=?', (scope.workspace_id, clinic['pa']['id']))
    if not record:
        from services.database import execute
        await execute("INSERT INTO clinical_records(id,workspace_id,unit_id,patient_id,allergies,diagnoses,clinical_notes,created_by,created_at,updated_at) VALUES('record',?,?,?,?,?,?,?,?,?)", (scope.workspace_id, clinic['a'], clinic['pa']['id'], 'penicillin', 'migraine', 'note', '1', '2026-10-06T00:00:00Z', '2026-10-06T00:00:00Z'))
    result = await clinic_migration.migrate_workspace_async(scope, backup_reference='backup://synthetic', backup_confirmed=True)
    assert result['status'] == 'completed'
    again = await clinic_migration.migrate_workspace_async(scope, backup_reference='backup://synthetic-2', backup_confirmed=True)
    assert again['patients'] == 0
    patients = await fetch_all_sql("SELECT id FROM tasks WHERE workspace_id=? AND work_item_type='patient'", (scope.workspace_id,))
    assert patients
    rolled = await clinic_migration.rollback_run_async(scope, again['run_id'])
    assert rolled['status'] == 'rolled_back'
    with pytest.raises(ValueError, match='backup_required'):
        await clinic_migration.migrate_workspace_async(scope, backup_reference='', backup_confirmed=False)
