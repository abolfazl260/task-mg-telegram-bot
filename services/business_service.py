import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from config import BASE_DIR

logger = logging.getLogger(__name__)
DATA_FILE = BASE_DIR / "data" / "business_connections.json"


def _read_data():
    if not DATA_FILE.exists():
        return {"connections": {}, "messages": []}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read business connection data from %s", DATA_FILE)
        return {"connections": {}, "messages": []}
    data.setdefault("connections", {})
    data.setdefault("messages", [])
    return data


def _write_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=DATA_FILE.parent, delete=False) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(DATA_FILE)


def upsert_business_connection(connection):
    data = _read_data()
    data["connections"][connection.id] = {
        "id": connection.id,
        "user_id": connection.user.id,
        "user_chat_id": connection.user_chat_id,
        "username": connection.user.username or "",
        "full_name": connection.user.full_name or "",
        "date": connection.date.isoformat() if connection.date else "",
        "can_reply": bool(connection.can_reply),
        "is_enabled": bool(connection.is_enabled),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_data(data)
    return data["connections"][connection.id]


def get_business_connection(connection_id):
    return _read_data()["connections"].get(connection_id)


def record_business_message(message, event_type="business_message"):
    data = _read_data()
    entry = {
        "event_type": event_type,
        "business_connection_id": message.business_connection_id,
        "chat_id": message.chat_id,
        "message_id": message.message_id,
        "from_user_id": message.from_user.id if message.from_user else None,
        "from_username": message.from_user.username if message.from_user else "",
        "text": message.text or message.caption or "",
        "date": message.date.isoformat() if message.date else "",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    data["messages"].append(entry)
    data["messages"] = data["messages"][-500:]
    _write_data(data)
    return entry


def record_deleted_business_messages(deleted):
    data = _read_data()
    entry = {
        "event_type": "deleted_business_messages",
        "business_connection_id": deleted.business_connection_id,
        "chat_id": deleted.chat.id,
        "message_ids": list(deleted.message_ids),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    data["messages"].append(entry)
    data["messages"] = data["messages"][-500:]
    _write_data(data)
    return entry
