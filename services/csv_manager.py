"""Backward-compatible task storage facade; persistent storage is SQLite."""
from datetime import datetime
from services.database import sync_execute
from services.task_service import read_tasks,_write_all

def init_csv():
 from services.database import _run,init_db
 _run(init_db())
def save_task(data):
 from services.task_service import save_task as _save
 return _save(data)
def update_task_status(task_id,new_status):
 task=next((x for x in read_tasks() if x.get('id')==task_id),None)
 if not task:return False
 task['status']=new_status;task['completed_at']=datetime.now().strftime('%Y-%m-%d %H:%M') if new_status=='done' else ''
 _write_all(read_tasks());return True
def _read_all_tasks():return read_tasks()
def _write_all_tasks(tasks):return _write_all(tasks)
