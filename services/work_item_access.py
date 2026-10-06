"""Persisted role, branch and parent authorization for typed Work Items.

Policies are supplied by the owning bot profile. Unknown workspace roles fail
closed; personal/team tasks retain their existing TaskBot ACL.
"""
from __future__ import annotations

from services.database import fetch_all_sql, fetch_one_sql
from services.work_item_type_service import _profile_settings_async


async def policy_for_workspace(workspace_id):
    workspace = await fetch_one_sql("SELECT * FROM workspaces WHERE id=? AND status='active'", (workspace_id,))
    if not workspace:
        raise PermissionError("work_item_permission_denied")
    settings = await _profile_settings_async(workspace['bot_key'])
    return workspace, settings.get('work_item_access', {})


async def membership_roles(task, actor_id):
    if not task.get('workspace_id'):
        return []
    rows = await fetch_all_sql('SELECT role FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status=\'active\' AND (unit_id IS NULL OR unit_id=?)', (task['workspace_id'], str(actor_id), task.get('unit_id')))
    return [r['role'] for r in rows]


async def workspace_predicate(workspace_id, actor_id, *, alias='t', action='view'):
    if alias not in {'t', 's', 'p', 'e', 'c', 'f'} or action not in {'view', 'edit', 'report', 'manage_schema'}:
        raise ValueError('invalid_access_predicate')
    _workspace, policy = await policy_for_workspace(workspace_id)
    memberships = await fetch_all_sql('SELECT role,unit_id FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status=\'active\'', (workspace_id, str(actor_id)))
    terms, params = [], [workspace_id]
    for membership in memberships:
        rule = policy.get(membership['role'], {})
        if not rule.get(action):
            continue
        term = '1=1'
        if membership['unit_id']:
            term += f' AND {alias}.unit_id=?'
            params.append(membership['unit_id'])
        if rule.get('assigned_only'):
            # A child can be assigned directly, or inherit the root assignment.
            # A root can also be in scope through one of its assigned children.
            term += f''' AND ({alias}.assignee_id=? OR EXISTS(
                SELECT 1 FROM tasks ap WHERE ap.id={alias}.parent_task_id
                AND ap.workspace_id={alias}.workspace_id AND ap.unit_id={alias}.unit_id AND ap.assignee_id=?) OR EXISTS(
                SELECT 1 FROM tasks ac WHERE ac.parent_task_id={alias}.id
                AND ac.workspace_id={alias}.workspace_id AND ac.unit_id={alias}.unit_id AND ac.assignee_id=?) OR EXISTS(
                SELECT 1 FROM reference_entities ar WHERE ar.id={alias}.reference_id
                AND ar.workspace_id={alias}.workspace_id AND ar.unit_id={alias}.unit_id AND ar.primary_owner_user_id=?))'''
            params.extend([str(actor_id)] * 4)
        terms.append('(' + term + ')')
    if not terms:
        raise PermissionError('work_item_permission_denied')
    return f'{alias}.workspace_id=? AND (' + ' OR '.join(terms) + ')', tuple(params)


async def authorized_task(task_id, actor_id, *, write=False, workspace_id=None):
    task = await fetch_one_sql('SELECT * FROM tasks WHERE id=?', (str(task_id),))
    if not task or (workspace_id is not None and task.get('workspace_id') != workspace_id):
        raise PermissionError('work_item_permission_denied')
    if task.get('workspace_id'):
        pred, args = await workspace_predicate(task['workspace_id'], actor_id, action='edit' if write else 'view')
        if not await fetch_one_sql(f'SELECT 1 FROM tasks t WHERE {pred} AND t.id=?', args + (str(task_id),)):
            raise PermissionError('work_item_permission_denied')
        # Authorize the parent separately so child IDs cannot bypass its scope.
        if task.get('parent_task_id'):
            parent = await fetch_one_sql('SELECT * FROM tasks WHERE id=?', (task['parent_task_id'],))
            if not parent or parent.get('workspace_id') != task['workspace_id'] or parent.get('unit_id') != task['unit_id']:
                raise PermissionError('work_item_permission_denied')
            if not await fetch_one_sql(f'SELECT 1 FROM tasks t WHERE {pred} AND t.id=?', args + (parent['id'],)):
                raise PermissionError('work_item_permission_denied')
    else:
        from services.task_service import user_can_modify_task_async
        from services.team_service import ais_member
        can_access = await user_can_modify_task_async(actor_id, task)
        if not write and task.get('team_id'):
            can_access = await ais_member(task['team_id'], actor_id)
        if not can_access:
            raise PermissionError('work_item_permission_denied')
    return task


async def field_allowed(definition, task, actor_id, *, action='view'):
    import json
    if not task.get('workspace_id') and str(task.get('user_id')) == str(actor_id):
        return True
    roles = await membership_roles(task, actor_id)
    configured = definition.get(f'{action}_roles_json') or '[]'
    allowed = json.loads(configured) if isinstance(configured, str) else configured
    return not allowed or bool(set(allowed) & set(roles))
