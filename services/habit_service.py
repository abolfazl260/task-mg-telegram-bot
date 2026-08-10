import uuid
from datetime import date,datetime,timedelta
from services.database import sync_all,sync_one,sync_execute
TEMPLATES=[]
def is_habit_due_on(habit,day=None):
 day=day or date.today(); repeat=habit.get('repeat_type') or 'daily'
 try:start=datetime.strptime(habit.get('start_date') or date.today().isoformat(),'%Y-%m-%d').date()
 except ValueError:start=day
 if day<start:return False
 if repeat=='weekly':return day.weekday()==start.weekday()
 if repeat=='monthly':return day.day==start.day
 return True
def init_habits():
 from services.database import _run,init_db
 _run(init_db())
def create_habit(user_id,title,category='',description='',repeat_type='daily',target='',reminder_time='',start_date=''):
 hid=str(uuid.uuid4())[:8]; sync_execute('INSERT INTO habits(id,user_id,title,category,description,repeat_type,target,reminder_time,start_date,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(hid,str(user_id),title,category or '',description or '',repeat_type,target or '',reminder_time or '',start_date or date.today().isoformat(),1,datetime.now().strftime('%Y-%m-%d %H:%M')));return hid
def get_user_habits(user_id,active_only=False):return sync_all('habits','user_id=?'+(' AND active=1' if active_only else ''),(str(user_id),))
def get_habit(habit_id):return sync_one('habits','id=?',(habit_id,))
def update_habit(habit_id,**changes):
 allowed={'title','category','description','repeat_type','target','reminder_time','start_date','active'}; changes={k:v for k,v in changes.items() if k in allowed}
 if not changes:return False
 sets=','.join(f'{k}=?' for k in changes); sync_execute(f'UPDATE habits SET {sets} WHERE id=?',(*changes.values(),habit_id));return bool(sync_one('habits','id=?',(habit_id,)))
def delete_habit(habit_id):
 if not get_habit(habit_id):return False
 sync_execute('DELETE FROM habits WHERE id=?',(habit_id,));return True
def mark_done(habit_id,user_id,day=None):
 day=day or date.today().isoformat()
 if sync_one('habit_logs','habit_id=? AND user_id=? AND done_date=?',(habit_id,str(user_id),day)):return False
 sync_execute('INSERT INTO habit_logs(habit_id,user_id,done_date,done_at) VALUES(?,?,?,?)',(habit_id,str(user_id),day,datetime.now().strftime('%Y-%m-%d %H:%M')));return True
def get_logs(user_id=None,habit_id=None):
 w=[];p=[]
 if user_id is not None:w.append('user_id=?');p.append(str(user_id))
 if habit_id is not None:w.append('habit_id=?');p.append(habit_id)
 return sync_all('habit_logs',' AND '.join(w) if w else '',p)
def stats_for_habit(habit):
 logs=get_logs(habit_id=habit.get('id')); days=sorted({x.get('done_date') for x in logs if x.get('done_date')},reverse=True);today=date.today();cur=0;cursor=today
 if today.isoformat() not in days:cursor=today-timedelta(days=1)
 s=set(days)
 while cursor.isoformat() in s:cur+=1;cursor-=timedelta(days=1)
 best=run=0;prev=None
 for value in sorted(s):
  d=datetime.strptime(value,'%Y-%m-%d').date();run=run+1 if prev and d==prev+timedelta(days=1) else 1;best=max(best,run);prev=d
 return {'current':cur,'best':best,'total':len(logs),'last':max(days) if days else '—'}
def get_all_habit_user_ids():return sorted({x.get('user_id') for x in sync_all('habits') if x.get('user_id')})
