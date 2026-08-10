from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from services.database import sync_all, sync_one, sync_execute

DEFAULT_TIMEZONE = 'UTC'
DEFAULT_DATE_FORMAT = 'jalali'

def init_users():
    from services.database import _run, init_db
    _run(init_db())

def read_users():
    rows = sync_all('users')
    for row in rows:
        row['user_id'] = str(row.get('user_id',''))
        row['messages_count'] = str(row.get('messages_count') or 0)
        row['date_format'] = row.get('date_format') or DEFAULT_DATE_FORMAT
    return rows

def validate_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo((tz_name or '').strip()); return True
    except (ZoneInfoNotFoundError, ValueError): return False

def record_user(user, increment_usage=True):
    if not user: return False
    uid = str(user.id); now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    existing = sync_one('users','user_id=?',(uid,))
    if existing:
        count = int(existing.get('messages_count') or 0) + (1 if increment_usage else 0)
        sync_execute('UPDATE users SET full_name=?,username=?,last_seen=?,date_format=COALESCE(NULLIF(date_format,\'\'),?),messages_count=? WHERE user_id=?',(user.full_name or '',user.username or '',now,DEFAULT_DATE_FORMAT,count,uid))
        return False
    sync_execute('INSERT INTO users(user_id,full_name,username,timezone,date_format,first_seen,last_seen,messages_count) VALUES(?,?,?,?,?,?,?,?)',(uid,user.full_name or '',user.username or '',DEFAULT_TIMEZONE,DEFAULT_DATE_FORMAT,now,now,1 if increment_usage else 0))
    return True

def set_user_timezone(user_id, tz_name: str) -> bool:
    tz_name=(tz_name or '').strip()
    if not validate_timezone(tz_name): return False
    uid=str(user_id)
    if sync_one('users','user_id=?',(uid,)): sync_execute('UPDATE users SET timezone=? WHERE user_id=?',(tz_name,uid))
    else: sync_execute('INSERT INTO users(user_id,timezone,date_format,messages_count) VALUES(?,?,?,0)',(uid,tz_name,DEFAULT_DATE_FORMAT))
    return True

def get_user_timezone(user_id):
    row=sync_one('users','user_id=?',(str(user_id),)); return (row or {}).get('timezone') or DEFAULT_TIMEZONE

def set_user_date_format(user_id,date_format):
    value=(date_format or '').strip().lower()
    if value not in {'jalali','gregorian'}: return False
    uid=str(user_id)
    if sync_one('users','user_id=?',(uid,)): sync_execute('UPDATE users SET date_format=? WHERE user_id=?',(value,uid))
    else: sync_execute('INSERT INTO users(user_id,date_format,timezone,messages_count) VALUES(?,?,?,0)',(uid,value,DEFAULT_TIMEZONE))
    return True

def get_user_date_format(user_id):
    value=((sync_one('users','user_id=?',(str(user_id),)) or {}).get('date_format') or DEFAULT_DATE_FORMAT).lower()
    return value if value in {'jalali','gregorian'} else DEFAULT_DATE_FORMAT

def all_users(): return read_users()
