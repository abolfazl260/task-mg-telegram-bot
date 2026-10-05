from __future__ import annotations
import base64,hashlib,json,logging,re
from datetime import datetime,timezone
from urllib import error,parse,request
from bot_context import get_current_bot_key
from services.database import sync_all,sync_one,sync_execute
from services.task_service import read_tasks

logger=logging.getLogger(__name__)

STATUS_TO_JIRA={'pending':('pending','to do','open','new'),'in_progress':('in progress','in-progress','started'),'done':('done','closed','resolved'),'cancelled':('cancelled','canceled','closed')}
def _load_connections(): return sync_all('jira_connections')
def _save_connections(items):
 for x in items: sync_execute('UPDATE jira_connections SET base_url=?,identity=?,credential=?,project_key=?,deployment=?,issue_type=?,account_id=?,auth_method=?,connected_at=?,last_sync_at=? WHERE bot_key=? AND user_id=?',(x.get('base_url',''),x.get('identity',''),x.get('credential',''),x.get('project_key',''),x.get('deployment','cloud'),x.get('issue_type','Task'),x.get('account_id',''),x.get('auth_method','basic'),x.get('connected_at',''),x.get('last_sync_at',''),x.get('bot_key','default'),str(x.get('user_id'))))
def _load_links(): return sync_all('jira_task_links')
def _save_links(items):
 for x in items: sync_execute('UPDATE jira_task_links SET jira_key=?,sync_hash=?,updated_at=? WHERE bot_key=? AND task_id=?',(x.get('jira_key',''),x.get('sync_hash',''),x.get('updated_at',''),x.get('bot_key','default'),x.get('task_id')))
def get_connection(user_id,bot_key=None): return sync_one('jira_connections','bot_key=? AND user_id=?',(bot_key or get_current_bot_key(),str(user_id)))
def save_connection(user_id,base_url,identity,credential,project_key,deployment='cloud',issue_type='Task',account_id=''):
 base_url=base_url.strip().rstrip('/'); deployment=deployment.lower().strip()
 if deployment not in ('cloud','server'): raise ValueError('Jira deployment must be cloud or server')
 if not re.match(r'^https://[^/]+(?:/[^/]*)?$',base_url): raise ValueError('Jira URL must use HTTPS')
 if not identity.strip() or not credential.strip() or not project_key.strip(): raise ValueError('Jira URL, username/email, credential and project key are required.')
 row={'bot_key':get_current_bot_key() or 'default','user_id':str(user_id),'base_url':base_url,'identity':identity.strip(),'credential':credential.strip(),'project_key':project_key.strip().upper(),'deployment':deployment,'issue_type':issue_type.strip() or 'Task','account_id':account_id,'auth_method':'basic','connected_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'last_sync_at':''}
 old=get_connection(user_id,row['bot_key'])
 if old: sync_execute('UPDATE jira_connections SET base_url=?,identity=?,credential=?,project_key=?,deployment=?,issue_type=?,account_id=?,connected_at=?,last_sync_at=? WHERE bot_key=? AND user_id=?',(row['base_url'],row['identity'],row['credential'],row['project_key'],row['deployment'],row['issue_type'],row['account_id'],row['connected_at'],'',row['bot_key'],row['user_id']))
 else: sync_execute('INSERT INTO jira_connections(bot_key,user_id,base_url,identity,credential,project_key,deployment,issue_type,account_id,auth_method,connected_at,last_sync_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
 return row
def disconnect(user_id):
 bot=get_current_bot_key(); r=get_connection(user_id,bot)
 if not r: return False
 sync_execute('DELETE FROM jira_connections WHERE bot_key=? AND user_id=?',(bot,str(user_id))); return True
def _api_prefix(c): return '/rest/api/3' if c.get('deployment','cloud')=='cloud' else '/rest/api/2'
def _request_json(c,method,path,payload=None,query=None):
 url=c['base_url']+path+('?' + parse.urlencode(query) if query else '')
 auth='Bearer '+c['credential'] if c.get('deployment')=='server' and c.get('auth_method')=='pat' else 'Basic '+base64.b64encode(f"{c['identity']}:{c['credential']}".encode()).decode()
 body=None if payload is None else json.dumps(payload).encode(); req=request.Request(url,data=body,method=method.upper(),headers={'Authorization':auth,'Accept':'application/json','Content-Type':'application/json'})
 try:
  with request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode() or '{}')
 except error.HTTPError as e: raise RuntimeError(f'Jira API {e.code}: {e.read().decode(errors="replace")[:500]}')
def validate_connection(base_url,identity,credential,project_key,deployment='cloud',auth_method='basic'):
 c={'base_url':base_url.rstrip('/'),'identity':identity,'credential':credential,'project_key':project_key,'deployment':deployment,'auth_method':auth_method}; p='/rest/api/3' if deployment=='cloud' else '/rest/api/2'; me=_request_json(c,'GET',p+'/myself'); _request_json(c,'GET',f"{p}/project/{parse.quote(project_key,safe='')}"); return me if isinstance(me,dict) else {}
def _jira_due_date(deadline):
 m=re.search(r'(20\d\d[-/]\d{1,2}[-/]\d{1,2})',(deadline or '').strip()); return m.group(1).replace('/','-') if m else None
def _task_to_fields(task,c):
 d=task.get('description') or ''; f={'project':{'key':c['project_key']},'summary':task.get('title') or 'Telegram Task','issuetype':{'name':c.get('issue_type') or 'Task'}}
 f['description']=d if c.get('deployment')=='server' else {'type':'doc','version':1,'content':[{'type':'paragraph','content':[{'type':'text','text':d}]}]}; due=_jira_due_date(task.get('deadline',''))
 if due: f['duedate']=due
 return f
def _local_hash(t): return hashlib.sha256(json.dumps({k:t.get(k,'') for k in ('title','description','status','priority','deadline')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def _linked_task(tasks,key,bot_key):
 for t in tasks:
  if t.get('jira_key')==key: return t
 link=sync_one('jira_task_links','bot_key=? AND jira_key=?',(bot_key,key)); return next((t for t in tasks if t.get('id')==link.get('task_id')),None) if link else None
def _attach_links(tasks,bot_key):
 by={t.get('id'):t for t in tasks}
 for l in _load_links():
  if l.get('bot_key')==bot_key and l.get('task_id') in by: by[l['task_id']]['jira_key']=l.get('jira_key',''); by[l['task_id']]['jira_sync_hash']=l.get('sync_hash','')
def _persist_link(task,key,h,bot_key):
 old=sync_one('jira_task_links','bot_key=? AND task_id=?',(bot_key,task.get('id')))
 if old: sync_execute('UPDATE jira_task_links SET jira_key=?,sync_hash=?,updated_at=? WHERE bot_key=? AND task_id=?',(key,h,datetime.now(timezone.utc).isoformat(timespec='seconds'),bot_key,task.get('id')))
 else: sync_execute('INSERT INTO jira_task_links(bot_key,task_id,jira_key,sync_hash,updated_at) VALUES(?,?,?,?,?)',(bot_key,task.get('id'),key,h,datetime.now(timezone.utc).isoformat(timespec='seconds')))
def create_issue_for_task(task,user_id,bot_key=None):
 bot=bot_key or get_current_bot_key() or 'default'; c=get_connection(user_id,bot)
 if not c or task.get('jira_key'): return None
 p=_api_prefix(c); r=_request_json(c,'POST',p+'/issue',{'fields':_task_to_fields(task,c)}); key=r.get('key') if isinstance(r,dict) else None
 if key: _persist_link(task,key,_local_hash(task),bot)
 return key
def _jira_status_name(s): return STATUS_TO_JIRA.get(s,('pending',))[0]
def _find_transition(c,key,status):
 d=_request_json(c,'GET',f"{_api_prefix(c)}/issue/{parse.quote(key,safe='')}/transitions"); wanted={x.lower() for x in STATUS_TO_JIRA.get(status,())}
 for x in d.get('transitions',[]) if isinstance(d,dict) else []:
  n=(x.get('name') or '').lower(); to=((x.get('to') or {}).get('name') or '').lower()
  if n in wanted or to in wanted or _jira_status_name(status) in n: return x.get('id')
def update_issue_from_task(task,user_id,bot_key=None):
 bot=bot_key or get_current_bot_key() or 'default'; c=get_connection(user_id,bot); key=task.get('jira_key')
 if not c or not key: return False
 p=_api_prefix(c); f=_task_to_fields(task,c); f.pop('project',None); f.pop('issuetype',None); _request_json(c,'PUT',f"{p}/issue/{parse.quote(key,safe='')}",{'fields':f}); tid=_find_transition(c,key,task.get('status','pending'))
 if tid: _request_json(c,'POST',f"{p}/issue/{parse.quote(key,safe='')}/transitions",{'transition':{'id':tid}})
 _persist_link(task,key,_local_hash(task),bot); return True
def _map_jira_status(n):
 v=(n or '').lower()
 if any(x in v for x in ('done','closed','resolved','complete')): return 'done'
 if any(x in v for x in ('cancel','rejected')): return 'cancelled'
 if any(x in v for x in ('progress','started','development')): return 'in_progress'
 return 'pending'
def _description_text(issue):
 d=issue.get('fields',{}).get('description')
 if isinstance(d,str): return d
 def walk(n):
  if isinstance(n,dict): return n.get('text','') if n.get('type')=='text' else ''.join(walk(x) for x in n.get('content',[]))
  return ''.join(walk(x) for x in n) if isinstance(n,list) else ''
 return walk(d)
def _apply_issue_to_task(t,issue):
 f=issue.get('fields',{}); changed=False; vals={'title':f.get('summary') or t.get('title'),'description':_description_text(issue),'status':_map_jira_status((f.get('status') or {}).get('name','')),'deadline':f.get('duedate') or ''}; p=((f.get('priority') or {}).get('name','')).lower(); vals['priority']='high' if 'high' in p else 'low' if 'low' in p else 'medium'
 for k,v in vals.items():
  if v!=t.get(k): t[k]=v; changed=True
 if vals['status']=='done': t['completed_at']=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
 return changed
def _jira_issues_for_user(c,bot_key):
 links=[x.get('jira_key') for x in _load_links() if x.get('bot_key')==bot_key and x.get('jira_key')]; cl=' OR key in ('+','.join(links)+')' if links else ''; j=f"project = {c['project_key']} AND (assignee = currentUser(){cl}) ORDER BY updated DESC"; d=_request_json(c,'GET',_api_prefix(c)+'/search',query={'jql':j,'maxResults':100,'fields':'summary,description,status,duedate,priority,updated'}); return d.get('issues',[]) if isinstance(d,dict) else []
def _write_all(tasks,bot_key):
 current={str(t.get('id')):t for t in sync_all('tasks','bot_key=?',(bot_key,))}
 for task in tasks:
  tid=str(task.get('id') or '')
  if not tid: continue
  if tid in current:
   sync_execute('UPDATE tasks SET user_id=?,title=?,priority=?,status=?,deadline=?,category=?,tags=?,description=?,created_at=?,completed_at=?,team_id=?,assignee_id=?,assignee_name=?,assignee_username=? WHERE id=? AND bot_key=?',(str(task.get('user_id') or ''),task.get('title',''),task.get('priority','medium'),task.get('status','pending'),task.get('deadline',''),task.get('category',''),task.get('tags',''),task.get('description',''),task.get('created_at',''),task.get('completed_at',''),task.get('team_id') or None,task.get('assignee_id') or None,task.get('assignee_name',''),task.get('assignee_username',''),tid,bot_key))
  else:
   sync_execute('INSERT INTO tasks(id,bot_key,user_id,title,priority,status,deadline,category,tags,description,created_at,completed_at,team_id,assignee_id,assignee_name,assignee_username) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,bot_key,str(task.get('user_id') or ''),task.get('title',''),task.get('priority','medium'),task.get('status','pending'),task.get('deadline',''),task.get('category',''),task.get('tags',''),task.get('description',''),task.get('created_at',''),task.get('completed_at',''),task.get('team_id') or None,task.get('assignee_id') or None,task.get('assignee_name',''),task.get('assignee_username','')))
def sync_connection(c,bot_key=None):
 bot=bot_key or c.get('bot_key') or get_current_bot_key() or 'default'; tasks=read_tasks(); _attach_links(tasks,bot); by={t.get('jira_key'):t for t in tasks if t.get('jira_key')}; changed=0; failures=[]; inbound_links=[]
 for issue in _jira_issues_for_user(c,bot):
  key=issue.get('key'); t=by.get(key) or _linked_task(tasks,key,bot)
  if t:
   t['jira_key']=key; changed+=1 if _apply_issue_to_task(t,issue) else 0
  else:
   f=issue.get('fields',{}); t={'id':f'JIRA-{key}','user_id':str(c['user_id']),'title':f.get('summary') or key,'priority':'medium','status':_map_jira_status((f.get('status') or {}).get('name','')),'deadline':f.get('duedate') or '','category':'Jira','tags':'jira','description':_description_text(issue),'created_at':datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),'completed_at':'','team_id':'','assignee_id':'','assignee_name':'','assignee_username':'','jira_key':key}; tasks.append(t); by[key]=t; changed+=1
  inbound_links.append((t,key))
 if changed:
  try:_write_all(tasks,bot)
  except Exception as exc:
   logger.exception('Jira inbound persistence failed provider=jira user_id=%s bot_key=%s project=%s operation=persist_inbound exception_type=%s error=%s',c.get('user_id'),bot,c.get('project_key',''),type(exc).__name__,str(exc)[:500])
   failures.append({'task_id':'','jira_key':'','operation':'persist_inbound','error':type(exc).__name__})
   return {'success':False,'partial':False,'updated':0,'failed':len(failures),'errors':failures}
 for t,key in inbound_links:
  try:
   h=_local_hash(t); _persist_link(t,key,h,bot); t['jira_sync_hash']=h
  except Exception as exc:
   failures.append({'task_id':str(t.get('id') or ''),'jira_key':str(key or ''),'operation':'persist_link','error':type(exc).__name__})
   logger.exception('Jira link persistence failed provider=jira user_id=%s bot_key=%s project=%s jira_key=%s task_id=%s operation=persist_link exception_type=%s error=%s',c.get('user_id'),bot,c.get('project_key',''),key,t.get('id',''),type(exc).__name__,str(exc)[:500])
 for t in tasks:
  if str(t.get('user_id'))!=str(c['user_id']): continue
  try:
   if not t.get('jira_key'): t['jira_key']=create_issue_for_task(t,c['user_id'],bot) or ''
   elif t.get('jira_sync_hash')!=_local_hash(t): update_issue_from_task(t,c['user_id'],bot)
  except Exception as exc:
   operation='create_issue' if not t.get('jira_key') else 'update_issue'
   failures.append({'task_id':str(t.get('id') or ''),'jira_key':str(t.get('jira_key') or ''),'operation':operation,'error':type(exc).__name__})
   logger.exception('Jira sync task failed provider=jira user_id=%s bot_key=%s project=%s jira_key=%s task_id=%s operation=%s exception_type=%s error=%s',c.get('user_id'),bot,c.get('project_key',''),t.get('jira_key',''),t.get('id',''),operation,type(exc).__name__,str(exc)[:500])
 return {'success':not failures,'partial':bool(failures and changed),'updated':changed,'failed':len(failures),'errors':failures}
def sync_all_connections(bot_key=None):
 bot=bot_key or get_current_bot_key() or 'default'; cs=[x for x in _load_connections() if x.get('bot_key')==bot]; results=[]; updated=0; failed_connections=0
 for c in cs:
  try:
   result=sync_connection(c,bot); results.append({'user_id':str(c.get('user_id')),'project_key':c.get('project_key',''),**result}); updated+=int(result.get('updated') or 0)
   if result.get('success'): sync_execute('UPDATE jira_connections SET last_sync_at=? WHERE bot_key=? AND user_id=?',(datetime.now(timezone.utc).isoformat(timespec='seconds'),bot,str(c['user_id'])))
   else: failed_connections+=1
  except Exception as exc:
   failed_connections+=1; logger.exception('Jira connection sync failed provider=jira user_id=%s bot_key=%s project=%s operation=sync_connection exception_type=%s error=%s',c.get('user_id'),bot,c.get('project_key',''),type(exc).__name__,str(exc)[:500]); results.append({'user_id':str(c.get('user_id')),'project_key':c.get('project_key',''),'success':False,'partial':False,'updated':0,'failed':1,'errors':[{'operation':'sync_connection','error':type(exc).__name__}]})
 return {'success':failed_connections==0,'partial':0<failed_connections<len(cs),'updated':updated,'connections':len(cs),'failed_connections':failed_connections,'results':results}
