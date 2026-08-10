"""Backward-compatible facade; task persistence is SQLite only."""
def init_csv():
 from services.database import _run,init_db
 _run(init_db())
def save_task(data):
 from services.task_service import save_task as _save
 return _save(data)
def update_task_status(task_id,new_status):
 from services.task_service import update_task_status as _update
 return _update(task_id,new_status)
def _read_all_tasks():
 from services.task_service import read_tasks
 return read_tasks()
def _write_all(tasks):
 from services.task_service import _write_all as _write
 return _write(tasks)
