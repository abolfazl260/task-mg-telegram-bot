import pytest

from services import attachment_service as files
from services import task_attribute_service as attrs
from services import task_service
from services.database import transaction


@pytest.mark.asyncio
async def test_multiple_files_and_attribute_link(test_db, monkeypatch):
    monkeypatch.setattr(task_service, '_bot', lambda: 'clinic')
    tid = await task_service.create_task_async('1', 'Synthetic', 'medium', '', '', '', work_item_type='patient')
    definition = await attrs.create_attribute_definition_async('document', 'Document', 'text', bot_key='clinic', work_item_type='patient')
    first = await files.attach_file_async(tid, '1', file_id='opaque-1', filename='document.pdf', size_bytes=42, attribute_definition_id=definition['id'])
    second = await files.attach_file_async(tid, '1', file_id='opaque-2', metadata={'public_url': 'SECRET', 'token': 'SECRET', 'kind': 'scan'})
    assert len(await files.list_attachments_async(tid, '1')) == 2
    assert second['metadata'] == {'kind': 'scan'}
    assert first['filename'] == 'document.pdf'
    with pytest.raises(PermissionError):
        await files.get_attachment_async(first['id'], '99')
    await files.archive_attachment_async(first['id'], '1')
    assert await files.get_attachment_async(first['id'], '1') is None
    assert len(await files.list_attachments_async(tid, '1', include_archived=True)) == 2
    await files.unarchive_attachment_async(first['id'], '1')
    assert await files.get_attachment_async(first['id'], '1')


@pytest.mark.asyncio
async def test_branch_doctor_and_revocation_inheritance(clinic):
    c = clinic
    oid = c['owner'].workspace_id
    # A typed parent, child and unassigned parent in the same branch.
    await transaction([
        ("INSERT INTO tasks(id,bot_key,user_id,title,work_item_type,workspace_id,unit_id,reference_id,assignee_id) VALUES('p','clinic','1','Synthetic','patient',?,?,?,'4')", (oid,c['a'],c['pa']['id'])),
        ("INSERT INTO tasks(id,bot_key,user_id,title,work_item_type,workspace_id,unit_id,parent_task_id) VALUES('s','clinic','1','Synthetic session','session',?,?,'p')", (oid,c['a'])),
    ])
    a = await files.attach_file_async('s', '1', file_id='child-file')
    assert await files.get_attachment_async(a['id'], '4')
    for uid in ['6','8','999']:
        with pytest.raises(PermissionError):
            await files.get_attachment_async(a['id'], uid)
    await __import__('services.healthcare.service', fromlist=['set_membership']).set_membership(c['owner'], '4', 'doctor', c['a'], active=False)
    with pytest.raises(PermissionError):
        await files.get_attachment_async(a['id'], '4')


@pytest.mark.asyncio
async def test_attribute_scope_and_sensitive_file(clinic):
    c=clinic; oid=c['owner'].workspace_id
    await transaction([("INSERT INTO tasks(id,bot_key,user_id,title,work_item_type,workspace_id,unit_id,assignee_id) VALUES('p','clinic','1','Synthetic','patient',?,?,'4')",(oid,c['a']))])
    definition=await attrs.create_attribute_definition_async('diagnosis','Diagnosis','text',bot_key='clinic',workspace_id=oid,work_item_type='patient',view_roles=['owner','doctor'],edit_roles=['owner','doctor'])
    a=await files.attach_file_async('p','1',file_id='opaque',attribute_definition_id=definition['id'])
    assert await files.list_attachments_async('p','2') == []
    with pytest.raises(PermissionError):
        await files.get_attachment_async(a['id'],'2')
    with pytest.raises(PermissionError):
        await files.attach_file_async('p','2',file_id='opaque',attribute_definition_id=definition['id'])
    with pytest.raises(ValueError):
        await files.attach_file_async('p','1',file_id='opaque',attribute_definition_id='foreign')
