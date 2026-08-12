from datetime import datetime, timezone
import json
from services.database import sync_all, sync_one, sync_execute
from services.user_service import record_user


def upsert_business_connection(connection):
    uid = str(connection.user.id)
    row = {
        'id': connection.id,
        'user_id': uid,
        'user_chat_id': str(connection.user_chat_id or ''),
        'username': connection.user.username or '',
        'full_name': connection.user.full_name or '',
        'date': connection.date.isoformat() if connection.date else '',
        'can_reply': int(bool(connection.can_reply)),
        'is_enabled': int(bool(connection.is_enabled)),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    if sync_one('business_connections', 'id=?', (connection.id,)):
        sync_execute(
            'UPDATE business_connections SET user_id=?,user_chat_id=?,username=?,full_name=?,date=?,can_reply=?,is_enabled=?,updated_at=? WHERE id=?',
            (uid, row['user_chat_id'], row['username'], row['full_name'], row['date'], row['can_reply'], row['is_enabled'], row['updated_at'], connection.id),
        )
    else:
        sync_execute(
            'INSERT INTO business_connections(id,user_id,user_chat_id,username,full_name,date,can_reply,is_enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
            tuple(row.values()),
        )
    return row


def get_business_connection(connection_id):
    return sync_one('business_connections', 'id=?', (connection_id,))


def _ensure_business_connection(message):
    """Create a minimal connection record when a message arrives first."""
    user = message.from_user
    if user:
        record_user(user, increment_usage=False)

    sync_execute(
        '''INSERT OR IGNORE INTO business_connections(
               id,user_id,user_chat_id,username,full_name,date,can_reply,is_enabled,updated_at
           ) VALUES(?,?,?,?,?,?,?,?,?)''',
        (
            message.business_connection_id,
            str(user.id) if user else None,
            str(message.chat_id or ''),
            user.username or '' if user else '',
            user.full_name or '' if user else '',
            message.date.isoformat() if message.date else '',
            0,
            0,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def _record(entry):
    sync_execute(
        'INSERT INTO business_messages(event_type,business_connection_id,chat_id,message_id,from_user_id,from_username,text,message_ids_json,date,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (
            entry['event_type'],
            entry.get('business_connection_id'),
            str(entry.get('chat_id') or ''),
            str(entry.get('message_id') or ''),
            str(entry.get('from_user_id')) if entry.get('from_user_id') is not None else None,
            entry.get('from_username') or '',
            entry.get('text') or '',
            json.dumps(entry.get('message_ids', []), ensure_ascii=False),
            entry.get('date') or '',
            entry.get('recorded_at') or '',
        ),
    )
    return entry


def record_business_message(message, event_type='business_message'):
    # business_message may arrive before /start or before the corresponding
    # business_connection update. Both foreign-key parents must exist first.
    _ensure_business_connection(message)
    return _record({
        'event_type': event_type,
        'business_connection_id': message.business_connection_id,
        'chat_id': message.chat_id,
        'message_id': message.message_id,
        'from_user_id': message.from_user.id if message.from_user else None,
        'from_username': message.from_user.username if message.from_user else '',
        'text': message.text or message.caption or '',
        'date': message.date.isoformat() if message.date else '',
        'recorded_at': datetime.now(timezone.utc).isoformat(),
    })


def record_deleted_business_messages(deleted):
    # Deleted-message updates have no from_user; the connection itself must
    # still exist. If it was never observed, create a safe placeholder.
    sync_execute(
        '''INSERT OR IGNORE INTO business_connections(
               id,user_id,user_chat_id,username,full_name,date,can_reply,is_enabled,updated_at
           ) VALUES(?,?,?,?,?,?,?,?,?)''',
        (
            deleted.business_connection_id,
            None,
            '',
            '',
            '',
            '',
            0,
            0,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return _record({
        'event_type': 'deleted_business_messages',
        'business_connection_id': deleted.business_connection_id,
        'chat_id': deleted.chat.id,
        'message_ids': list(deleted.message_ids),
        'recorded_at': datetime.now(timezone.utc).isoformat(),
    })
