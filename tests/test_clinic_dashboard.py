from datetime import datetime, timezone

import pytest

from services import clinic_dashboard, clinic_typed


@pytest.mark.asyncio
async def test_dashboard_counts_match_typed_source(clinic):
    owner=clinic['owner']
    patient=await clinic_typed.create_patient_async(owner,clinic['a'],'Dashboard patient')
    scheduled_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    await clinic_typed.create_child_async(owner,patient['id'],'session','Today',scheduled_at=scheduled_at)
    await clinic_typed.create_child_async(owner,patient['id'],'followup','Due',fields={'due_at':'2020-01-01T00:00:00Z'})
    result=await clinic_dashboard.dashboard_async(owner.workspace_id,'1')
    assert result['patients']['total'] >= 1
    assert result['sessions']['today'] >= 1
    assert result['followups']['overdue'] >= 1
