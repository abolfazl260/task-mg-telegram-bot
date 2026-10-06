import json,logging,os,secrets,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
from services.database import sync_all as db_sync_all,sync_one,sync_execute,sync_execute_returning_one
logger=logging.getLogger(__name__)
_bots={}
_PENDING_STATE_TTL=900
_MAX_PENDING_STATES=1000
MICROSOFT_AUTH='https://login.microsoftonline.com/common/oauth2/v2.0/authorize';MICROSOFT_TOKEN='https://login.microsoftonline.com/common/oauth2/v2.0/token';MICROSOFT_GRAPH='https://graph.microsoft.com/v1.0';GOOGLE_AUTH='https://accounts.google.com/o/oauth2/v2/auth';GOOGLE_TOKEN='https://oauth2.googleapis.com/token';GOOGLE_TASKS='https://tasks.googleapis.com/tasks/v1'
def _cleanup_pending_states(now=None):
 now=float(now if now is not None else time.time())
 sync_execute('DELETE FROM oauth_pending_states WHERE created_at<?',(now-_PENDING_STATE_TTL,))
 rows=db_sync_all('oauth_pending_states')
 excess=len(rows)-_MAX_PENDING_STATES
 if excess>0:
  for pending in sorted(rows,key=lambda item:float(item.get('created_at') or 0))[:excess]:
   sync_execute('DELETE FROM oauth_pending_states WHERE state=?',(pending['state'],))
def _store_pending_state(state,provider,user_id,bot_key,created):
 sync_execute('INSERT INTO oauth_pending_states(state,provider,user_id,bot_key,created_at) VALUES(?,?,?,?,?)',(state,provider,str(user_id),bot_key,float(created)))
def _consume_pending_state(state):
 return sync_execute_returning_one('DELETE FROM oauth_pending_states WHERE state=? RETURNING state,provider,user_id,bot_key,created_at',(state,))
def init_integrations():
 from services.database import sync_all as _sync_all
 _sync_all('external_connections')
def _read_integrations():return db_sync_all('external_connections')
def _read_user_tasks(user_id):return db_sync_all('tasks','user_id=?',(str(user_id),))
def _write_integrations(rows):
 for r in rows:
  sync_execute('UPDATE external_connections SET access_token=?,refresh_token=?,expires_at=?,external_list_id=?,external_list_name=?,enabled=?,last_sync=? WHERE user_id=? AND bot_key=? AND provider=?',(r.get('access_token',''),r.get('refresh_token',''),r.get('expires_at',''),r.get('external_list_id',''),r.get('external_list_name',''),int(r.get('enabled') or 0),r.get('last_sync',''),str(r.get('user_id')),r.get('bot_key') or 'default',r.get('provider')))
def get_connection(user_id,provider,bot_key='default'):return sync_one('external_connections','user_id=? AND provider=? AND bot_key=?',(str(user_id),provider,bot_key))
def connected(user_id,provider,bot_key='default'):
 r=get_connection(user_id,provider,bot_key);return bool(r and int(r.get('enabled') or 0)==1 and r.get('refresh_token'))
def disconnect(user_id,provider,bot_key='default'):
 r=get_connection(user_id,provider,bot_key)
 if not r:return False
 sync_execute('UPDATE external_connections SET enabled=0,access_token=\'\',refresh_token=\'\',expires_at=\'\' WHERE user_id=? AND provider=? AND bot_key=?',(str(user_id),provider,bot_key));return True
def _redirect_uri(provider):
 base=os.getenv('INTEGRATION_REDIRECT_BASE_URL','').rstrip('/')
 if not base:raise RuntimeError('INTEGRATION_REDIRECT_BASE_URL تنظیم نشده است')
 return f'{base}/integrations/oauth/{provider}'
def start_oauth(provider,user_id,bot_key='default'):
 if provider not in ('microsoft','google'):raise ValueError('ارائه‌دهنده نامعتبر است')
 now=time.time();state=secrets.token_urlsafe(32);_store_pending_state(state,provider,user_id,bot_key,now);_cleanup_pending_states(now)
 if provider=='microsoft':params={'client_id':os.getenv('MICROSOFT_CLIENT_ID',''),'response_type':'code','redirect_uri':_redirect_uri(provider),'response_mode':'query','scope':'offline_access User.Read Tasks.ReadWrite','state':state};return MICROSOFT_AUTH+'?'+urllib.parse.urlencode(params)
 params={'client_id':os.getenv('GOOGLE_TASKS_CLIENT_ID',''),'response_type':'code','redirect_uri':_redirect_uri(provider),'scope':'https://www.googleapis.com/auth/tasks','access_type':'offline','prompt':'consent','state':state};return GOOGLE_AUTH+'?'+urllib.parse.urlencode(params)
def _post_form(url,data):
 req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode())
def complete_oauth(provider,code,state):
 p=_consume_pending_state(state)
 if not p or p['provider']!=provider or time.time()-float(p['created_at'])>600:raise ValueError('درخواست اتصال منقضی یا نامعتبر است')
 if provider=='microsoft':data=_post_form(MICROSOFT_TOKEN,{'client_id':os.getenv('MICROSOFT_CLIENT_ID',''),'client_secret':os.getenv('MICROSOFT_CLIENT_SECRET',''),'grant_type':'authorization_code','code':code,'redirect_uri':_redirect_uri(provider),'scope':'offline_access User.Read Tasks.ReadWrite'})
 else:data=_post_form(GOOGLE_TOKEN,{'client_id':os.getenv('GOOGLE_TASKS_CLIENT_ID',''),'client_secret':os.getenv('GOOGLE_TASKS_CLIENT_SECRET',''),'grant_type':'authorization_code','code':code,'redirect_uri':_redirect_uri(provider)})
 if 'access_token' not in data:raise RuntimeError(data.get('error_description') or data.get('error') or 'دریافت دسترسی ناموفق بود')
 exp=str(int(time.time())+int(data.get('expires_in',3600))-60);r=get_connection(p['user_id'],provider,p['bot_key'])
 if r:sync_execute('UPDATE external_connections SET access_token=?,refresh_token=?,expires_at=?,enabled=1,last_sync=\'\' WHERE user_id=? AND provider=? AND bot_key=?',(data['access_token'],data.get('refresh_token') or r.get('refresh_token',''),exp,p['user_id'],provider,p['bot_key']))
 else:sync_execute('INSERT INTO external_connections(user_id,bot_key,provider,access_token,refresh_token,expires_at,enabled) VALUES(?,?,?,?,?,?,1)',(p['user_id'],p['bot_key'],provider,data['access_token'],data.get('refresh_token',''),exp))
 return p
def register_bot(bot_key,bot):_bots[bot_key]=bot
def _refresh(row):
 if row.get('expires_at') and int(float(row['expires_at']))>int(time.time()):return row.get('access_token')
 refresh=row.get('refresh_token')
 if not refresh:return row.get('access_token')
 token=MICROSOFT_TOKEN if row['provider']=='microsoft' else GOOGLE_TOKEN;data=_post_form(token,{'client_id':os.getenv('MICROSOFT_CLIENT_ID' if row['provider']=='microsoft' else 'GOOGLE_TASKS_CLIENT_ID',''),'client_secret':os.getenv('MICROSOFT_CLIENT_SECRET' if row['provider']=='microsoft' else 'GOOGLE_TASKS_CLIENT_SECRET',''),'grant_type':'refresh_token','refresh_token':refresh});
 if 'access_token' not in data:raise RuntimeError('تمدید دسترسی ناموفق بود')
 exp=str(int(time.time())+int(data.get('expires_in',3600))-60);sync_execute('UPDATE external_connections SET access_token=?,expires_at=? WHERE user_id=? AND provider=? AND bot_key=?',(data['access_token'],exp,row['user_id'],row['provider'],row['bot_key']));row['access_token']=data['access_token'];return row['access_token']
def _request_json(url,token,method='GET',payload=None):
 body=json.dumps(payload).encode() if payload is not None else None;req=urllib.request.Request(url,data=body,headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode() or '{}')
def _microsoft_lists(token):return _request_json(f'{MICROSOFT_GRAPH}/me/todo/lists',token).get('value',[])
def _google_lists(token):return _request_json(f'{GOOGLE_TASKS}/users/@me/lists?maxResults=100',token).get('items',[])
def get_lists(user_id,provider,bot_key='default'):
 r=get_connection(user_id,provider,bot_key);return [] if not r else (_microsoft_lists(_refresh(r)) if provider=='microsoft' else _google_lists(_refresh(r)))
def set_list(user_id,provider,list_id,list_name,bot_key='default'):
 if not get_connection(user_id,provider,bot_key):return False
 sync_execute('UPDATE external_connections SET external_list_id=?,external_list_name=? WHERE user_id=? AND provider=? AND bot_key=?',(list_id,list_name,str(user_id),provider,bot_key));return True
def _ensure_list(row,lists):
 if row.get('external_list_id'):return row['external_list_id']
 if not lists:raise RuntimeError('هیچ فهرستی در سرویس مقصد پیدا نشد')
 x=lists[0];set_list(row['user_id'],row['provider'],x.get('id'),x.get('displayName') or x.get('title') or '',row['bot_key']);row['external_list_id']=x.get('id');return row['external_list_id']
def _deadline_iso(value,google=False):
 try:dt=datetime.strptime(value.strip(),'%Y-%m-%d %H:%M')
 except (ValueError,TypeError,AttributeError):
  try:dt=datetime.strptime(value.strip(),'%Y-%m-%d')
  except (ValueError,TypeError,AttributeError):return value
 return dt.strftime('%Y-%m-%dT%H:%M:%SZ') if google else dt.strftime('%Y-%m-%dT%H:%M:%S')
def _task_marker(local_task_id):return f'[BOT_TASK:{local_task_id}]'
def _notes_with_marker(text,local_task_id):
 marker=_task_marker(local_task_id);text=(text or '').rstrip()
 return text if marker in text else (f'{text}\n\n{marker}' if text else marker)
def _load_task_links(user_id,bot_key,provider):return db_sync_all('external_task_links','user_id=? AND bot_key=? AND provider=?',(str(user_id),bot_key,provider))
def _save_task_link(user_id,bot_key,provider,local_task_id,external_task_id,external_list_id):
 now=datetime.now(timezone.utc).isoformat(timespec='seconds')
 try:
  sync_execute('INSERT INTO external_task_links(user_id,bot_key,provider,local_task_id,external_task_id,external_list_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id,bot_key,provider,local_task_id) DO UPDATE SET external_task_id=excluded.external_task_id,external_list_id=excluded.external_list_id,updated_at=excluded.updated_at',(str(user_id),bot_key,provider,str(local_task_id),str(external_task_id),str(external_list_id or ''),now,now))
 except Exception as exc:
  logger.exception('External task link persistence failed provider=%s bot_key=%s user_id=%s local_task_id=%s external_task_id=%s operation=save_link exception_type=%s',provider,bot_key,user_id,local_task_id,external_task_id,type(exc).__name__)
  raise
def _get_external(row,external_task_id,token,list_id):
 eid=urllib.parse.quote(str(external_task_id),safe='');lid=urllib.parse.quote(str(list_id),safe='')
 if row['provider']=='microsoft':return _request_json(f'{MICROSOFT_GRAPH}/me/todo/lists/{lid}/tasks/{eid}',token)
 return _request_json(f'{GOOGLE_TASKS}/lists/{lid}/tasks/{eid}',token)
def _create_external(row,task):
 token=_refresh(row);lists=_microsoft_lists(token) if row['provider']=='microsoft' else _google_lists(token);lid=_ensure_list(row,lists);d=_notes_with_marker(task.get('description') or '',task.get('id'))
 if row['provider']=='microsoft':
  p={'title':task.get('title') or 'بدون عنوان','body':{'content':d,'contentType':'text'}}
  if task.get('deadline'):p['dueDateTime']={'dateTime':_deadline_iso(task['deadline']),'timeZone':'UTC'}
  return _request_json(f"{MICROSOFT_GRAPH}/me/todo/lists/{urllib.parse.quote(lid,safe='')}/tasks",token,'POST',p)
 p={'title':task.get('title') or 'بدون عنوان','notes':d}
 if task.get('deadline'):p['due']=_deadline_iso(task['deadline'],True)
 return _request_json(f"{GOOGLE_TASKS}/lists/{urllib.parse.quote(lid,safe='')}/tasks",token,'POST',p)
def _sync_provider_names(provider=None,providers=None):
 if provider is not None:return [provider] if provider in ('microsoft','google') else []
 if providers is None:return ['microsoft','google']
 return [name for name in providers if name in ('microsoft','google')]
def sync_user(user_id,bot_key='default',provider=None,providers=None):
 results=[];tasks=None
 for name in _sync_provider_names(provider,providers):
  row=get_connection(user_id,name,bot_key)
  if not row or int(row.get('enabled') or 0)!=1:continue
  try:
   token=_refresh(row);lists=_microsoft_lists(token) if name=='microsoft' else _google_lists(token);lid=_ensure_list(row,lists);ext=_request_json(f"{MICROSOFT_GRAPH}/me/todo/lists/{urllib.parse.quote(lid,safe='')}/tasks?$top=100",token).get('value',[]) if name=='microsoft' else _request_json(f"{GOOGLE_TASKS}/lists/{urllib.parse.quote(lid,safe='')}/tasks?maxResults=100",token).get('items',[])
   markers={};external_by_id={}
   for x in ext:
    if x.get('id') is not None:external_by_id[str(x.get('id'))]=x
    notes=x.get('body',{}).get('content','') if name=='microsoft' else x.get('notes','')
    if '[BOT_TASK:' in notes:markers[notes.split('[BOT_TASK:',1)[1].split(']',1)[0]]=x
   links={str(x.get('local_task_id')):x for x in _load_task_links(user_id,bot_key,name)}
   if tasks is None:tasks=_read_user_tasks(user_id)
   changed=0
   for t in tasks:
    if str(t.get('user_id'))!=str(user_id):continue
    local_id=str(t.get('id') or '')
    if not local_id:continue
    link=links.get(local_id);x=None
    if link and link.get('external_task_id'):
     external_id=str(link.get('external_task_id'));x=external_by_id.get(external_id)
     if x is None:
      try:x=_get_external(row,external_id,token,lid)
      except urllib.error.HTTPError as exc:
       if exc.code not in (404,410):raise
    if x is None:
     legacy=markers.get(local_id)
     if legacy and legacy.get('id') is not None:
      external_id=str(legacy.get('id'));_save_task_link(user_id,bot_key,name,local_id,external_id,lid);links[local_id]={'local_task_id':local_id,'external_task_id':external_id};x=legacy
     else:
      created=_create_external(row,t);external_id=str(created.get('id') or '')
      if not external_id:raise RuntimeError(f'{name} task creation returned no id')
      _save_task_link(user_id,bot_key,name,local_id,external_id,lid);links[local_id]={'local_task_id':local_id,'external_task_id':external_id};x=created;changed+=1
    done=x.get('status')=='completed'
    if done and t.get('status')!='done':
     sync_execute('UPDATE tasks SET status=?,completed_at=? WHERE id=? AND bot_key=?',('done',datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),t.get('id'),bot_key));t['status']='done';changed+=1
    elif not done and t.get('status')=='done':
     sync_execute('UPDATE tasks SET status=?,completed_at=? WHERE id=? AND bot_key=?',('pending','',t.get('id'),bot_key));t['status']='pending';t['completed_at']='';changed+=1
   sync_execute('UPDATE external_connections SET last_sync=? WHERE user_id=? AND provider=? AND bot_key=?',(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),str(user_id),name,bot_key));results.append((name,changed,None))
  except Exception as exc:
   logger.exception('External sync failed provider=%s bot_key=%s user_id=%s operation=sync exception_type=%s',name,bot_key,user_id,type(exc).__name__)
   results.append((name,0,str(exc)))
 return results
def sync_all(bot_key='default',providers=None):
 names=_sync_provider_names(providers=providers);allowed=set(names)
 users=sorted({x['user_id'] for x in _read_integrations() if x.get('bot_key')==bot_key and int(x.get('enabled') or 0)==1 and x.get('provider') in allowed})
 return [(u,sync_user(u,bot_key,providers=names)) for u in users]
