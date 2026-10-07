import pytest

from services import clinic_setup, clinic_typed
from services import task_attribute_service as attributes
from services.database import fetch_one_sql
from services.healthcare import service


@pytest.mark.asyncio
async def test_patient_session_followup_lifecycle_and_scope(clinic):
    owner = clinic['owner']
    patient = await clinic_typed.create_patient_async(owner, clinic['a'], 'Typed Patient', doctor_id='4', reference_id=clinic['pa']['id'])
    assert patient['work_item_type'] == 'patient'
    session = await clinic_typed.create_child_async(owner, patient['id'], 'session', 'Initial visit', scheduled_at='2026-10-07T10:00:00+03:30', doctor_id='4', fields={'session_type': 'consultation'})
    followup = await clinic_typed.create_child_async(owner, patient['id'], 'followup', 'Call patient', fields={'due_at': '2026-10-08T10:00:00Z', 'dedupe_key': 'call-1'})
    listing = await clinic_typed.list_children_async(patient['id'], '4')
    assert listing['total'] == 2
    assert {row['work_item_type'] for row in listing['items']} == {'session', 'followup'}
    session = await clinic_typed.reschedule_async(session['id'], '4', '2026-10-08T10:00:00+03:30')
    assert session['typed']['status'] == 'rescheduled'
    session = await clinic_typed.transition_async(session['id'], '4', 'completed', fields={'actual_ended_at': '2026-10-08T11:00:00Z'})
    assert session['status'] == 'completed'
    with pytest.raises(PermissionError):
        await clinic_typed.list_children_async(patient['id'], '6')
    await service.set_membership(owner, '4', 'doctor', clinic['a'], active=False)
    with pytest.raises(PermissionError):
        await clinic_typed.transition_async(followup['id'], '4', 'completed')


@pytest.mark.asyncio
async def test_typed_parent_scope_and_no_generic_leak(clinic):
    owner = clinic['owner']
    a = await clinic_typed.create_patient_async(owner, clinic['a'], 'A typed')
    with pytest.raises(ValueError, match='invalid_work_item_type'):
        await clinic_typed.create_child_async(owner, a['id'], 'invalid', 'bad')
    # The typed storage has no effect on a generic TaskBot list.
    row = await fetch_one_sql('SELECT work_item_type FROM tasks WHERE id=?', (a['id'],))
    assert row['work_item_type'] == 'patient'



@pytest.mark.asyncio
async def test_medical_fields_use_core_attributes_and_respect_field_permissions(clinic):
    owner = clinic['owner']
    await clinic_setup._ensure_definitions(owner.workspace_id, 'clinic')

    patient = await clinic_typed.create_patient_async(
        owner,
        clinic['a'],
        'Medical Attribute Patient',
        doctor_id='4',
        fields={
            'allergies': 'Penicillin',
            'chronic_conditions': 'Asthma',
            'clinical_notes': 'Sensitive owner note',
        },
    )

    raw = await fetch_one_sql(
        'SELECT data_json FROM typed_work_item_data WHERE task_id=?',
        (patient['id'],),
    )
    assert 'Penicillin' not in raw['data_json']
    assert 'Asthma' not in raw['data_json']
    assert 'Sensitive owner note' not in raw['data_json']

    stored = {
        row['field_key']: row['value']
        for row in await attributes.get_task_attributes_async(patient['id'], '1')
    }
    assert stored['allergies'] == 'Penicillin'
    assert stored['chronic_conditions'] == 'Asthma'
    assert stored['clinical_notes'] == 'Sensitive owner note'
    assert patient['medical_attributes']['allergies'] == 'Penicillin'
    assert patient['typed']['clinical_notes'] == 'Sensitive owner note'

    reception_view = await clinic_typed._item(patient['id'], '2')
    assert 'allergies' not in reception_view['medical_attributes']
    assert 'chronic_conditions' not in reception_view['typed']
    assert 'clinical_notes' not in reception_view['typed']

    with pytest.raises(PermissionError, match='attribute_field_edit_denied'):
        await clinic_typed.update_item_async(
            patient['id'], '2', fields={'allergies': 'Should be denied'}
        )


@pytest.mark.asyncio
async def test_session_clinical_notes_are_attribute_backed_and_not_exposed_in_lists(clinic):
    owner = clinic['owner']
    await clinic_setup._ensure_definitions(owner.workspace_id, 'clinic')
    patient = await clinic_typed.create_patient_async(
        owner, clinic['a'], 'Session Medical Patient', doctor_id='4'
    )
    session = await clinic_typed.create_child_async(
        owner,
        patient['id'],
        'session',
        'Clinical visit',
        scheduled_at='2026-10-07T10:00:00+03:30',
        doctor_id='4',
        fields={'clinical_notes': 'Doctor-only session note'},
    )

    raw = await fetch_one_sql(
        'SELECT data_json FROM typed_work_item_data WHERE task_id=?',
        (session['id'],),
    )
    assert 'Doctor-only session note' not in raw['data_json']

    doctor_view = await clinic_typed._item(session['id'], '4')
    assert doctor_view['medical_attributes']['clinical_notes'] == 'Doctor-only session note'

    reception_view = await clinic_typed._item(session['id'], '2')
    assert 'clinical_notes' not in reception_view['typed']

    children = await clinic_typed.list_children_async(patient['id'], '2')
    listed_session = next(item for item in children['items'] if item['id'] == session['id'])
    assert 'clinical_notes' not in listed_session['typed']
