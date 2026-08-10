import json,uuid
from datetime import datetime
from bot_context import get_current_bot_key
from services.database import sync_all,sync_one,sync_execute,sync_transaction
from services.team_service import get_user_teams,can_edit,is_member,get_team
VALID_STATUSES={'pending','in_progress','done','cancelled'}
def _now():return datetime.now().strftime('%Y-%m-%d %H:%M')
def _bot():return get_current_bot_key() or 'default'
def _ensure_user(uid):
 uid=str(uid)
 if not sync_one('users','user_id=?',(uid,)):sync_execute('INSERT INTO users(user_id,timezone,date_format) VALUES(?,?,?)',(uid,'UTC','jalali'))
def read_tasks():return sync_all('tasks','bot_key=?',(_bot(),))
def save_task(data):
 v=list(data)+['']*20;_ensure_user(v[1]);sync_execute('INSERT INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(_bot(),*v[:15]))
def _write_all(tasks):
 sync_transaction([('UPDATE tasks SET user_id=?,title=?,priority=?,status=?,deadline=?,category=?,tags=?,description=?,created_at=?,completed_at=?,team_id=?,assignee_id=?,assignee_name=?,assignee_username=?,jira_key=?,jira_sync_hash=? WHERE id=? AND bot_key=?',(str(t.get('user_id') or ''),t.get('title') or '',t.get('priority') or 'medium',t.get('status') or 'pending',t.get('deadline') or '',t.get('category') or '',t.get('tags') or '',t.get('description') or '',t.get('created_at') or '',t.get('completed_at') or '',t.get('team_id') or None,t.get('assignee_id') or None,t.get('assignee_name') or '',t.get('assignee_username') or '',t.get('jira_key') or '',t.get('jira_sync_hash') or '',t.get('id'),_bot())) for t in tasks])
def update_task_status(task_id,new_status):
 if new_status not in VALID_STATUSES or not sync_one('tasks','id=? AND bot_key=?',(task_id,_bot())):return False
 sync_execute('UPDATE tasks SET status=?,completed_at=? WHERE id=? AND bot_key=?',(new_status,_now() if new_status=='done' else '',task_id,_bot()));return True
def create_task(user_id,title,priority,deadline,category,tags,description='',team_id='',assignee=None):
 _ensure_user(user_id);tid=str(uuid.uuid4())[:8]
 if team_id and not category:
  t=get_team(team_id);category=t.get('name','') if t else category
 aid=str((assignee or {}).get('user_id') or '') or None
 if aid:_ensure_user(aid)
 sync_execute('INSERT INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,_bot(),str(user_id),title,priority,'pending',deadline or '',category or '',tags or '',description or '',_now(),team_id or None,aid,(assignee or {}).get('display_name') or '',(assignee or {}).get('username') or ''))
 if assignee:_history(tid,user_id,'assigned','',(assignee or {}).get('display_name') or '')
 return tid
def _visible(user_id,team_id=None,active=False):
 if team_id:
  if not is_member(team_id,user_id):return []
  return sync_all('tasks','bot_key=? AND team_id=?'+(' AND status IN (\'pending\',\'in_progress\')' if active else ''),(_bot(),team_id))
 ids={x['team']['team_id'] for x in get_user_teams(user_id)};uid=str(user_id);rows=read_tasks();return [x for x in rows if (not active or x.get('status') in ('pending','in_progress')) and ((x.get('team_id') or '') in ids or (not x.get('team_id') and str(x.get('user_id'))==uid))]
def get_active_tasks(user_id,team_id=None):return _visible(user_id,team_id,True)
def get_all_user_tasks(user_id,team_id=None):return _visible(user_id,team_id,False)
def get_team_tasks(team_id,active_only=True):return sync_all('tasks','bot_key=? AND team_id=?'+(' AND status IN (\'pending\',\'in_progress\')' if active_only else ''),(_bot(),team_id))
def get_task_by_id(task_id):return sync_one('tasks','id=? AND bot_key=?',(task_id,_bot()))
def user_can_modify_task(user_id,task):return bool(task and (can_edit(task.get('team_id'),user_id) if task.get('team_id') else str(task.get('user_id'))==str(user_id)))
def change_task_status(task_id,new_status):return update_task_status(task_id,new_status)
def search_tasks(user_id,query):
 q=(query or '').strip().lower();return [t for t in get_all_user_tasks(user_id) if q and q in ' '.join(str(t.get(k) or '') for k in ('title','category','tags','description')).lower()]
def get_all_user_ids():return sorted({str(t.get('user_id')) for t in read_tasks() if t.get('user_id')})
def _history(task_id,actor,action,old,new):
 _ensure_user(actor);sync_execute('INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)',(task_id,str(actor),action,old,new,_now()))
def assign_task(task_id,assignee,actor_id,action='assigned'):
 t=get_task_by_id(task_id)
 if not t:return False
 aid=str((assignee or {}).get('user_id') or '') or None
 if aid:_ensure_user(aid)
 sync_execute('UPDATE tasks SET assignee_id=?,assignee_name=?,assignee_username=? WHERE id=? AND bot_key=?',(aid,(assignee or {}).get('display_name') or '',(assignee or {}).get('username') or '',task_id,_bot()));_history(task_id,actor_id,action,t.get('assignee_name') or '',(assignee or {}).get('display_name') or '');return True
def get_unassigned_tasks(user_id):return [t for t in get_active_tasks(user_id) if not t.get('assignee_id')]
def get_task_comments(task_id):
 out=[]
 for r in sync_all('task_comments','task_id=? ORDER BY id',(task_id,)):
  try:c=json.loads(r.get('content_json') or '{}')
  except Exception:c={}
  out.append({'author_id':str(r.get('author_id') or ''),'author_name':r.get('author_name') or 'کاربر','author_username':r.get('author_username') or '','created_at':r.get('created_at') or '',**c})
 return out
def add_task_comment(task_id,author,content):
 if not get_task_by_id(task_id):return False
 aid=str(author.get('id') or author.get('user_id') or '') or None
 if aid:_ensure_user(aid)
 sync_execute('INSERT INTO task_comments(task_id,author_id,author_name,author_username,content_json,created_at) VALUES(?,?,?,?,?,?)',(task_id,aid,author.get('full_name') or author.get('display_name') or 'کاربر',author.get('username') or '',json.dumps(content,ensure_ascii=False),_now()));return True
def link_user_category_to_team(user_id,category,team_id):
 n=0
 for t in get_all_user_tasks(user_id):
  if not t.get('team_id') and (t.get('category') or '').strip().lower()==(category or '').strip().lower():sync_execute('UPDATE tasks SET team_id=? WHERE id=? AND bot_key=?',(team_id,t['id'],_bot()));n+=1
 return n
def link_team_name_category_for_owner(team_id):
 t=get_team(team_id);return link_user_category_to_team(t['owner_id'],t['name'],team_id) if t else 0
def get_assignment_history(task_id):return sync_all('task_assignment_history','task_id=? ORDER BY id',(task_id,))
