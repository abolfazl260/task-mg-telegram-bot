"""Read-only, allowlisted database explorer for the Admin Back Office."""
from __future__ import annotations

from typing import Any

from services.database import get_db

MAX_PAGE_SIZE = 100
MAX_OFFSET = 1_000_000
MAX_FILTERS = 12
MAX_FILTER_VALUE_LENGTH = 500

TABLE_SPECS: dict[str, dict[str, Any]] = {
    "users": {
        "label": "Users",
        "columns": {
            "user_id": "text", "full_name": "text", "username": "text",
            "timezone": "text", "date_format": "text",
            "first_seen": "datetime", "last_seen": "datetime",
            "messages_count": "number",
        },
        "default_sort": "last_seen", "default_direction": "desc",
    },
    "teams": {
        "label": "Teams",
        "columns": {
            "team_id": "text", "name": "text", "owner_id": "text",
            "created_at": "datetime",
        },
        "default_sort": "created_at", "default_direction": "desc",
    },
    "team_members": {
        "label": "Team Members",
        "columns": {
            "team_id": "text", "user_id": "text", "role": "text",
            "display_name": "text", "username": "text", "joined_at": "datetime",
        },
        "default_sort": "joined_at", "default_direction": "desc",
    },
    "tasks": {
        "label": "Tasks (Core only)",
        "columns": {
            "id": "text", "bot_key": "text", "user_id": "text", "title": "text",
            "priority": "text", "status": "text", "deadline": "datetime",
            "category": "text", "tags": "text", "created_at": "datetime",
            "completed_at": "datetime", "team_id": "text", "assignee_id": "text",
            "assignee_name": "text", "assignee_username": "text", "jira_key": "text",
        },
        "scope_sql": '"organization_id" IS NULL',
        "default_sort": "created_at", "default_direction": "desc",
    },
    "task_assignment_history": {
        "label": "Task Assignment History",
        "columns": {
            "id": "number", "task_id": "text", "actor_id": "text", "action": "text",
            "old_assignee_name": "text", "new_assignee_name": "text",
            "created_at": "datetime",
        },
        "default_sort": "id", "default_direction": "desc",
    },
    "custom_bots": {
        "label": "Managed Bots",
        "columns": {
            "bot_key": "text", "owner_user_id": "text", "owner_name": "text",
            "owner_username": "text", "bot_username": "text", "features": "text",
            "status": "text", "pricing_plan": "text", "created_at": "datetime",
            "updated_at": "datetime",
        },
        "default_sort": "updated_at", "default_direction": "desc",
    },
}

OPERATORS = {
    "text": ("contains", "exact"),
    "number": ("equals", "greater_than", "less_than", "range"),
    "datetime": ("before", "after", "range"),
    "boolean": ("equals",),
}


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


async def _available_columns(table: str) -> list[dict[str, Any]]:
    spec = TABLE_SPECS[table]
    db = await get_db()
    async with db.conn.execute(f"PRAGMA table_info({_quote_identifier(table)})") as cur:
        actual = {str(row[1]) for row in await cur.fetchall()}
    return [
        {"name": name, "type": kind, "operators": list(OPERATORS[kind])}
        for name, kind in spec["columns"].items()
        if name in actual
    ]


async def database_explorer_tables() -> dict[str, Any]:
    tables = []
    for name, spec in TABLE_SPECS.items():
        columns = await _available_columns(name)
        if columns:
            tables.append({
                "name": name,
                "label": spec["label"],
                "columns": columns,
                "default_sort": spec.get("default_sort", columns[0]["name"]),
                "default_direction": spec.get("default_direction", "asc"),
            })
    return {
        "tables": tables,
        "readonly": True,
        "max_page_size": MAX_PAGE_SIZE,
        "max_filters": MAX_FILTERS,
    }


def _text_value(value: Any) -> str:
    text = str(value if value is not None else "")
    if not text or len(text) > MAX_FILTER_VALUE_LENGTH:
        raise ValueError("invalid_filter_value")
    return text


def _number_value(value: Any) -> int | float:
    if isinstance(value, bool):
        raise TypeError("invalid_number_filter")
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        raise ValueError("invalid_number_filter") from None
    return int(number) if number.is_integer() else number


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_filter(column: str, kind: str, operator: str, item: dict[str, Any]) -> tuple[str, list[Any]]:
    quoted = _quote_identifier(column)
    if operator not in OPERATORS[kind]:
        raise ValueError("invalid_filter_operator")
    if kind == "text":
        value = _text_value(item.get("value"))
        if operator == "contains":
            return f"{quoted} LIKE ? ESCAPE '\\'", [f"%{_escape_like(value)}%"]
        return f"{quoted} = ?", [value]
    if kind == "number":
        if operator == "range":
            lower, upper = _number_value(item.get("value")), _number_value(item.get("value_to"))
            if lower > upper:
                raise ValueError("invalid_filter_range")
            return f"{quoted} BETWEEN ? AND ?", [lower, upper]
        value = _number_value(item.get("value"))
        sql_operator = {"equals": "=", "greater_than": ">", "less_than": "<"}[operator]
        return f"{quoted} {sql_operator} ?", [value]
    if kind == "datetime":
        if operator == "range":
            lower, upper = _text_value(item.get("value")), _text_value(item.get("value_to"))
            if lower > upper:
                raise ValueError("invalid_filter_range")
            return f"{quoted} BETWEEN ? AND ?", [lower, upper]
        value = _text_value(item.get("value"))
        sql_operator = {"before": "<", "after": ">"}[operator]
        return f"{quoted} {sql_operator} ?", [value]
    value = str(item.get("value", "")).strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError("invalid_boolean_filter")
    return f"{quoted} = ?", [1 if value in {"true", "1"} else 0]


async def database_explorer_rows(
    table: str,
    *,
    filters: list[dict[str, Any]] | None = None,
    sort: str = "",
    direction: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if table not in TABLE_SPECS:
        raise ValueError("invalid_database_table")
    if not isinstance(limit, int) or limit < 1 or not isinstance(offset, int) or offset < 0 or offset > MAX_OFFSET:
        raise ValueError("invalid_pagination")
    limit = min(limit, MAX_PAGE_SIZE)
    spec = TABLE_SPECS[table]
    columns = await _available_columns(table)
    column_types = {column["name"]: column["type"] for column in columns}
    if not column_types:
        raise ValueError("database_table_unavailable")

    sort = sort or str(spec.get("default_sort") or next(iter(column_types)))
    if sort not in column_types:
        raise ValueError("invalid_sort_column")
    direction = (direction or str(spec.get("default_direction") or "asc")).lower()
    if direction not in {"asc", "desc"}:
        raise ValueError("invalid_sort_direction")

    filters = [] if filters is None else filters
    if not isinstance(filters, list) or len(filters) > MAX_FILTERS:
        raise ValueError("invalid_filters")

    clauses, params = [], []
    scope_sql = str(spec.get("scope_sql") or "").strip()
    if scope_sql:
        clauses.append(scope_sql)
    for item in filters:
        if not isinstance(item, dict):
            raise TypeError("invalid_filters")
        column, operator = str(item.get("column") or ""), str(item.get("operator") or "")
        if column not in column_types:
            raise ValueError("invalid_filter_column")
        clause, values = _build_filter(column, column_types[column], operator, item)
        clauses.append(clause)
        params.extend(values)

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    projection = ", ".join(_quote_identifier(column["name"]) for column in columns)
    table_sql = _quote_identifier(table)
    order_sql = f" ORDER BY {_quote_identifier(sort)} {direction.upper()}"
    db = await get_db()
    async with db.conn.execute(f"SELECT COUNT(*) FROM {table_sql}{where_sql}", tuple(params)) as cur:
        total = int((await cur.fetchone())[0])
    async with db.conn.execute(
        f"SELECT {projection} FROM {table_sql}{where_sql}{order_sql} LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ) as cur:
        rows = [dict(row) for row in await cur.fetchall()]
    return {
        "table": table, "columns": columns, "rows": rows, "total": total,
        "limit": limit, "offset": offset, "sort": sort, "direction": direction,
        "readonly": True,
    }
