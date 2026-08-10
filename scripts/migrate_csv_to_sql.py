from __future__ import annotations
import argparse,asyncio,csv,json,shutil
from pathlib import Path
import aiosqlite
from services.database import SCHEMA,DB_PATH
DATA=Path('data')
def csv_rows(name):
 p=DATA/name
 if not p.exists():return []
 with p.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def json_data(name,default):
 p=DATA/name
 if not p.exists():return default
 try:return json.loads(p.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return default
def s(v):return '' if v is None else str(v)
async def ensure_user(db,uid,name='',username=''):
 if uid is not None and s(uid):await db.execute('INSERT OR IGNORE INTO users(user_id,full_name,username,timezone,date_format,messages_count) VALUES(?,?,?,?,?,0)',(s(uid),name or '',username or '','UTC','jalali'))
async def migrate(output:Path):
 output.parent.mkdir(parents=True,exist_ok=True)
 async with aiosqlite.connect(output) as db:
  await db.executescript(SCHEMA);await db.execute('PRAGMA foreign_keys=ON');await db.execute('BEGIN IMMEDIATE')
  try:
   for r in csv_rows('users.csv'):await db.execute('INSERT OR REPLACE INTO users(user_id,full_name,username,timezone,date_format,first_seen,last_seen,messages_count) VALUES(?,?,?,?,?,?,?,?)',(s(r.get('user_id')),r.get('full_name',''),r.get('username',''),r.get('timezone') or 'UTC',r.get('date_format') or 'jalali',s(r.get('first_seen')),s(r.get('last_seen')),int(r.get('messages_count') or 0)))
   for r in csv_rows('teams.csv'):
    await ensure_user(db,r.get('owner_id'));await db.execute('INSERT OR REPLACE INTO teams(team_id,name,owner_id,editor_code,viewer_code,created_at) VALUES(?,?,?,?,?,?)',(r.get('team_id'),r.get('name',''),s(r.get('owner_id')),r.get('editor_code',''),r.get('viewer_code',''),s(r.get('created_at'))))
   for r in csv_rows('team_members.csv'):
    await ensure_user(db,r.get('user_id'),r.get('display_name',''),r.get('username',''));await db.execute('INSERT OR REPLACE INTO team_members(team_id,user_id,role,display_name,username,joined_at) VALUES(?,?,?,?,?,?)',(r.get('team_id'),s(r.get('user_id')),r.get('role') or 'viewer',r.get('display_name',''),r.get('username',''),s(r.get('joined_at'))))
   for r in csv_rows('tasks.csv'):
    await ensure_user(db,r.get('user_id'));await ensure_user(db,r.get('assignee_id'),r.get('assignee_name',''),r.get('assignee_username',''))
    await db.execute('INSERT OR REPLACE INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(r.get('id'),r.get('bot_key') or 'default',s(r.get('user_id')),r.get('title',''),r.get('priority') or 'medium',r.get('status') or 'pending',s(r.get('deadline')),r.get('category',''),r.get('tags',''),r.get('description',''),s(r.get('created_at')),s(r.get('completed_at')),r.get('team_id') or None,r.get('assignee_id') or None,r.get('assignee_name',''),r.get('assignee_username','')))
    for line in (r.get('assignment_history') or '').splitlines():
     p=line.split('|',4)
     if len(p)==5:
      ts,actor,action,old_name,new_name=p;await ensure_user(db,actor);await db.execute('INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)',(r.get('id'),s(actor),action,old_name,new_name,ts))
    try:comments=json.loads(r.get('comments') or '[]')
    except json.JSONDecodeError:comments=[]
    for c in comments if isinstance(comments,list) else []:
     aid=c.get('author_id') or c.get('user_id');await ensure_user(db,aid,c.get('author_name',''),c.get('author_username',''));meta={k:v for k,v in c.items() if k not in {'author_id','user_id','author_name','author_username','created_at'}}
     await db.execute('INSERT INTO task_comments(task_id,author_id,author_name,author_username,content_json,created_at) VALUES(?,?,?,?,?,?)',(r.get('id'),s(aid) if aid else None,c.get('author_name',''),c.get('author_username',''),json.dumps(meta,ensure_ascii=False),s(c.get('created_at'))))
   for r in csv_rows('habits.csv'):
    await ensure_user(db,r.get('user_id'));await db.execute('INSERT OR REPLACE INTO habits(id,user_id,title,category,description,repeat_type,target,reminder_time,start_date,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r.get('id'),s(r.get('user_id')),r.get('title',''),r.get('category',''),r.get('description',''),r.get('repeat_type') or 'daily',r.get('target',''),r.get('reminder_time',''),s(r.get('start_date')),int(r.get('active') or 0),s(r.get('created_at'))))
   for r in csv_rows('habit_logs.csv'):
    await ensure_user(db,r.get('user_id'));await db.execute('INSERT OR IGNORE INTO habit_logs(habit_id,user_id,done_date,done_at) VALUES(?,?,?,?)',(r.get('habit_id'),s(r.get('user_id')),s(r.get('done_date')),s(r.get('done_at'))))
   for r in csv_rows('custom_bots.csv'):
    await ensure_user(db,r.get('owner_user_id'),r.get('owner_name',''),r.get('owner_username',''));await db.execute('INSERT OR REPLACE INTO custom_bots(bot_key,owner_user_id,owner_name,owner_username,bot_token,bot_username,features,status,pricing_plan,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r.get('bot_key'),s(r.get('owner_user_id')),r.get('owner_name',''),r.get('owner_username',''),r.get('bot_token',''),r.get('bot_username',''),r.get('features',''),r.get('status') or 'active',r.get('pricing_plan') or 'free_beta',s(r.get('created_at')),s(r.get('updated_at'))))
   for r in csv_rows('integrations.csv'):
    await ensure_user(db,r.get('user_id'));await db.execute('INSERT OR REPLACE INTO external_connections(user_id,bot_key,provider,access_token,refresh_token,expires_at,external_list_id,external_list_name,enabled,last_sync) VALUES(?,?,?,?,?,?,?,?,?,?)',(s(r.get('user_id')),r.get('bot_key') or 'default',r.get('provider'),r.get('access_token',''),r.get('refresh_token',''),r.get('expires_at',''),r.get('external_list_id',''),r.get('external_list_name',''),int(r.get('enabled') or 0),r.get('last_sync','')))
   for r in json_data('jira_connections.json',[]):
    await ensure_user(db,r.get('user_id'));await db.execute('INSERT OR REPLACE INTO jira_connections(bot_key,user_id,base_url,identity,credential,project_key,deployment,issue_type,account_id,auth_method,connected_at,last_sync_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(r.get('bot_key') or 'default',s(r.get('user_id')),r.get('base_url',''),r.get('identity',''),r.get('credential',''),r.get('project_key',''),r.get('deployment') or 'cloud',r.get('issue_type') or 'Task',r.get('account_id',''),r.get('auth_method') or 'basic',s(r.get('connected_at')),s(r.get('last_sync_at'))))
   for r in json_data('jira_task_links.json',[]):await db.execute('INSERT OR REPLACE INTO jira_task_links(bot_key,task_id,jira_key,sync_hash,updated_at) VALUES(?,?,?,?,?)',(r.get('bot_key') or 'default',r.get('task_id'),r.get('jira_key'),r.get('sync_hash',''),s(r.get('updated_at'))))
   business=json_data('business_connections.json',{})
   for r in (business.get('connections') or {}).values():
    await ensure_user(db,r.get('user_id'),r.get('full_name',''),r.get('username',''));await db.execute('INSERT OR REPLACE INTO business_connections(id,user_id,user_chat_id,username,full_name,date,can_reply,is_enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(r.get('id'),s(r.get('user_id')) if r.get('user_id') is not None else None,s(r.get('user_chat_id')),r.get('username',''),r.get('full_name',''),s(r.get('date')),int(bool(r.get('can_reply'))),int(bool(r.get('is_enabled'))),s(r.get('updated_at'))))
   for r in business.get('messages') or []:
    await ensure_user(db,r.get('from_user_id'),'',r.get('from_username',''));await db.execute('INSERT INTO business_messages(event_type,business_connection_id,chat_id,message_id,from_user_id,from_username,text,message_ids_json,date,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(r.get('event_type',''),r.get('business_connection_id'),s(r.get('chat_id')),s(r.get('message_id')),s(r.get('from_user_id')) if r.get('from_user_id') is not None else None,r.get('from_username',''),r.get('text',''),json.dumps(r.get('message_ids',[]),ensure_ascii=False),s(r.get('date')),s(r.get('recorded_at'))))
   await db.commit()
  except Exception:await db.rollback();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',default=str(DB_PATH));p.add_argument('--backup',action='store_true');a=p.parse_args();out=Path(a.output)
 if a.backup and out.exists():shutil.copy2(out,out.with_suffix('.bak'))
 asyncio.run(migrate(out));print(f'Migration complete: {out}')
