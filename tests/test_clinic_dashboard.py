import pytest

from services import clinic_dashboard, clinic_typed


@pytest.mark.asyncio
async def test_dashboard_counts_match_typed_source(clinic):
    owner=clinic['owner']
    patient=await clinic_typed.create_patient_async(owner,clinic['a'],'Dashboard patient')
    await clinic_typed.create_child_async(owner,patient['id'],'session','Today',scheduled_at='2026-10-06T10:00:00Z')
    await clinic_typed.create_child_async(owner,patient['id'],'followup','Due',fields={'due_at':'2020-01-01T00:00:00Z'})
    result=await clinic_dashboard.dashboard_async(owner.workspace_id,'1')
    assert result['patients']['total'] >= 1
    assert result['sessions']['today'] >= 1
    assert result['followups']['overdue'] >= 1
