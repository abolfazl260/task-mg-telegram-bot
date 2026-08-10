from __future__ import annotations
import argparse,asyncio,csv,json,shutil
from datetime import datetime
from pathlib import Path
import aiosqlite
from services.database import SCHEMA,DB_PATH

DATA=Path('data')

def csv_rows(name):
 p=DATA/name
 if not p.exists(): return []
 with p.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def json_data(name,default):
 p=DATA/name
 if not p.exists():return default
 try:return json.loads(p.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return default

def iso(v):
 if not v:return ''
 return str(v)

def ensure_user(db,uid,full_name='',username=''):
 if not uid:return
 db.execute('INSERT OR IGNORE INTO users(user_id,full_name,username,timezone,date_format,messages_count) VALUES(?,?,?,?,?,0)',(str(uid),full_name or '',username or '','UTC','jalali'))

async def migrate(output:Path):
 output.parent.mkdir(parents=True,exist_ok=True)
 async with aiosqlite.connect(output) as db:
  await db.executescript(SCHEMA); await db.execute('PRAGMA foreign_keys=ON'); await db.commit()
  users=csv_rows('users.csv')
  for r in users: await db.execute('INSERT OR REPLACE INTO users(user_id,full_name,username,timezone,date_format,first_seen,last_seen,messages_count) VALUES(?,?,?,?,?,?,?,?)',(str(r.get('user_id') or ''),r.get('full_name',''),r.get('username',''),r.get('timezone') or 'UTC',r.get('date_format') or 'jalali',iso(r.get('first_seen')),iso(r.get('last_seen')),int(r.get('messages_count') or 0)))
  for r in csv_rows('teams.csv'):
   ensure_user(db,r.get('owner_id'))
   await db.execute('INSERT OR REPLACE INTO teams(team_id,name,owner_id,editor_code,viewer_code,created_at) VALUES(?,?,?,?,?,?)',(r.get('team_id'),r.get('name',''),str(r.get('owner_id')),r.get('editor_code',''),r.get('viewer_code',''),iso(r.get('created_at'))))
  await db.commit()
  for r in csv_rows('team_members.csv'):
   ensure_user(db,r.get('user_id'),r.get('display_name',''),r.get('username',''))
   await db.execute('INSERT OR REPLACE INTO team_members(team_id,user_id,role,display_name,username,joined_at) VALUES(?,?,?,?,?,?)',(r.get('team_id'),str(r.get('user_id')),r.get('role') or 'viewer',r.get('display_name',''),r.get('username',''),iso(r.get('joined_at'))))
  tasks=csv_rows('tasks.csv')
  for r in tasks:
   ensure_user(db,r.get('user_id'),r.get('assignee_name',''),r.get('assignee_username','')); ensure_user(db,r.get('assignee_id'),r.get('assignee_name',''),r.get('assignee_username',''))
   await db.execute('INSERT OR REPLACE INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(r.get('id'),r.get('bot_key') or 'default',str(r.get('user_id')),r.get('title',''),r.get('priority') or 'medium',r.get('status') or 'pending',iso(r.get('deadline')),r.get('category',''),r.get('tags',''),r.get('description',''),iso(r.get('created_at')),iso(r.get('completed_at')),r.get('team_id') or None,r.get('assignee_id') or None,r.get('assignee_name',''),r.get('assignee_username','')))
   history=r.get('assignment_history') or ''
   for line in history.splitlines():
    parts=line.split('|',4)
    if len(parts)>=5:
     ts,actor,action,old_name,new_name=parts; ensure_user(db,actor)
     await db.execute('INSERT INTO task_assignment_history(task_id,actor_id,action,old_assignee_name,new_assignee_name,created_at) VALUES(?,?,?,?,?,?)',(r.get('id'),str(actor),action,old_name,new_name,ts))
   try: comments=json.loads(r.get('comments') or '[]')
   except json.JSONDecodeError: comments=[]
   for c in comments if isinstance(comments,list) else []:
    aid=c.get('author_id') or c.get('user_id'); ensure_user(db,aid,c.get('author_name',''),c.get('author_username',''))
    meta={k:v for k,v in c.items() if k not in {'author_id','user_id','author_name','author_username','created_at'}}
    await db.execute('INSERT INTO task_comments(task_id,author_id,author_name,author_username,content_json,created_at) VALUES(?,?,?,?,?,?)',(r.get('id'),str(aid) if aid else None,c.get('author_name',''),c.get('author_username',''),json.dumps(meta,ensure_ascii=False),iso(c.get('created_at'))))
  for r in csv_rows('habits.csv'):
   ensure_user(db,r.get('user_id')); await db.execute('INSERT OR REPLACE INTO habits(id,user_id,title,category,description,repeat_type,target,reminder_time,start_date,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r.get('id'),str(r.get('user_id')),r.get('title',''),r.get('category',''),r.get('description',''),r.get('repeat_type') or 'daily',r.get('target',''),r.get('reminder_time',''),iso(r.get('start_date')),int(r.get('active') or 0),iso(r.get('created_at'))))
  for r in csv_rows('habit_logs.csv'):
   ensure_user(db,r.get('user_id')); await db.execute('INSERT OR IGNORE INTO habit_logs(habit_id,user_id,done_date,done_at) VALUES(?,?,?,?)',(r.get('habit_id'),str(r.get('user_id')),iso(r.get('done_date')),iso(r.get('done_at'))))
  for r in csv_rows('custom_bots.csv'):
   ensure_user(db,r.get('owner_user_id'),r.get('owner_name',''),r.get('owner_username','')); await db.execute('INSERT OR REPLACE INTO custom_bots(bot_key,owner_user_id,owner_name,owner_username,bot_token,bot_username,features,status,pricing_plan,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r.get('bot_key'),str(r.get('owner_user_id')),r.get('owner_name',''),r.get('owner_username',''),r.get('bot_token',''),r.get('bot_username',''),r.get('features',''),r.get('status') or 'active',r.get('pricing_plan') or 'free_beta',iso(r.get('created_at')),iso(r.get('updated_at'))))
  for r in csv_rows('integrations.csv'):
   ensure_user(db,r.get('user_id')); await db.execute('CREATE TABLE IF NOT EXISTS external_connections(user_id TEXT NOT NULL,bot_key TEXT NOT NULL,provider TEXT NOT NULL,access_token TEXT NOT NULL DEFAULT \'\',refresh_token TEXT NOT NULL DEFAULT \'\',expires_at TEXT NOT NULL DEFAULT \'\',external_list_id TEXT NOT NULL DEFAULT \'\',external_list_name TEXT NOT NULL DEFAULT \'\',enabled INTEGER NOT NULL DEFAULT 0,last_sync TEXT NOT NULL DEFAULT \'\',PRIMARY KEY(user_id,bot_key,provider))'); await db.execute('INSERT OR REPLACE INTO external_connections VALUES(?,?,?,?,?,?,?,?,?,?)',(str(r.get('user_id')),r.get('bot_key') or 'default',r.get('provider'),r.get('access_token',''),r.get('refresh_token',''),r.get('expires_at',''),r.get('external_list_id',''),r.get('external_list_name',''),int(r.get('enabled') or 0),r.get('last_sync','')))
  for name in ('jira_connections.json','jira_task_links.json'):
   pass
  for r in json_data('jira_connections.json',[]):
   ensure_user(db,r.get('user_id')); await db.execute('INSERT OR REPLACE INTO jira_connections(bot_key,user_id,base_url,identity,credential,project_key,deployment,issue_type,account_id,auth_method,connected_at,last_sync_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(r.get('bot_key') or 'default',str(r.get('user_id')),r.get('base_url',''),r.get('identity',''),r.get('credential',''),r.get('project_key',''),r.get('deployment') or 'cloud',r.get('issue_type') or 'Task',r.get('account_id',''),r.get('auth_method') or 'basic',iso(r.get('connected_at')),iso(r.get('last_sync_at'))))
  for r in json_data('jira_task_links.json',[]): await db.execute('INSERT OR REPLACE INTO jira_task_links(bot_key,task_id,jira_key,sync_hash,updated_at) VALUES(?,?,?,?,?)',(r.get('bot_key') or 'default',r.get('task_id'),r.get('jira_key'),r.get('sync_hash',''),iso(r.get('updated_at'))))
  business=json_data('business_connections.json',{})
  for r in (business.get('connections') or {}).values():
   ensure_user(db,r.get('user_id'),r.get('full_name',''),r.get('username','')); await db.execute('INSERT OR REPLACE INTO business_connections(id,user_id,user_chat_id,username,full_name,date,can_reply,is_enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(r.get('id'),str(r.get('user_id')) if r.get('user_id') is not None else None,str(r.get('user_chat_id') or ''),r.get('username',''),r.get('full_name',''),iso(r.get('date')),int(bool(r.get('can_reply'))),int(bool(r.get('is_enabled'))),iso(r.get('updated_at'))))
  for r in business.get('messages') or []:
   ensure_user(db,r.get('from_user_id'),'',r.get('from_username','')); await db.execute('INSERT INTO business_messages(event_type,business_connection_id,chat_id,message_id,from_user_id,from_username,text,message_ids_json,date,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(r.get('event_type',''),r.get('business_connection_id'),str(r.get('chat_id') or ''),str(r.get('message_id') or ''),str(r.get('from_user_id')) if r.get('from_user_id') is not None else None,r.get('from_username',''),r.get('text',''),json.dumps(r.get('message_ids',[]),ensure_ascii=False),iso(r.get('date')),iso(r.get('recorded_at'))))
  await db.commit()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(DB_PATH));parser.add_argument('--backup',action='store_true');args=parser.parse_args();out=Path(args.output)
 if args.backup and out.exists():shutil.copy2(out,out.with_suffix('.bak'))
 asyncio.run(migrate(out));print(f'Migration complete: {out}')
