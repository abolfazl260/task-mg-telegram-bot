import pytest

from services import clinic_typed
from services.healthcare import service
from services.healthcare.access import Scope
from services.database import fetch_one_sql


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
