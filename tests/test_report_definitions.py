import pytest

from services import report_definition_service as reports
from services.database import execute


@pytest.mark.asyncio
async def test_report_definition_is_db_side_and_scope_aware(clinic):
    scope=clinic['owner']
    from services.healthcare import service
    await service.create_action(scope, clinic['ca']['id'], 'Session', '3', '2026-10-06T10:00:00Z')
    await execute("UPDATE tasks SET work_item_type='session',status='completed',created_at='2026-10-06T10:00:00Z' WHERE workspace_id=? AND case_id=?", (scope.workspace_id, clinic['ca']['id']))
    definition=await reports.create_report_definition_async(name='sessions_by_status',title='Sessions by status',source_item_type='session',created_by='1',workspace_id=scope.workspace_id,bot_key='clinic',group_by='status',filters={'unit_id': {'eq': clinic['a']}},date_field='created_at',metric='count')
    result=await reports.execute_report_async(definition['id'],'1',from_date='2026-10-01',to_date='2026-10-31')
    assert result['summary']['value'] >= 1
    assert result['groups']
    assert result['rows']
    with pytest.raises(PermissionError):
        await reports.execute_report_async(definition['id'],'999')


@pytest.mark.asyncio
async def test_report_rejects_unsafe_fields_and_empty_dataset(clinic):
    scope=clinic['owner']
    with pytest.raises(ValueError, match='invalid_report_group_by'):
        await reports.create_report_definition_async(name='bad',title='Bad',source_item_type='task',created_by='1',workspace_id=scope.workspace_id,group_by='drop table')
    definition=await reports.create_report_definition_async(name='empty',title='Empty',source_item_type='task',created_by='1',workspace_id=scope.workspace_id,bot_key='clinic',filters={'status':'missing'})
    result=await reports.execute_report_async(definition['id'],'1')
    assert result['summary']['value'] == 0
    assert result['summary']['empty'] is True
