from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "handlers" / "task.py",
    ROOT / "handlers" / "team.py",
    ROOT / "handlers" / "task_pagination.py",
    ROOT / "handlers" / "search_share.py",
    ROOT / "handlers" / "extra_reports.py",
    ROOT / "handlers" / "habits.py",
    ROOT / "handlers" / "integrations.py",
    ROOT / "handlers" / "jira.py",
    ROOT / "handlers" / "custom_bot.py",
    ROOT / "handlers" / "business.py",
    ROOT / "handlers" / "start.py",
]

MAPPINGS = {
    "task_service": {
        "create_task": "create_task_async",
        "get_active_tasks": "get_active_tasks_async",
        "get_all_user_tasks": "get_all_user_tasks_async",
        "get_team_tasks": "get_team_tasks_async",
        "get_task_by_id": "get_task_by_id_async",
        "user_can_modify_task": "user_can_modify_task_async",
        "change_task_status": "change_task_status_async",
        "search_tasks": "search_tasks_async",
        "get_all_user_ids": "get_all_user_ids_async",
        "assign_task": "assign_task_async",
        "get_unassigned_tasks": "get_unassigned_tasks_async",
        "get_task_comments": "get_task_comments_async",
        "add_task_comment": "add_task_comment_async",
        "link_user_category_to_team": "link_user_category_to_team_async",
        "link_team_name_category_for_owner": "link_team_name_category_for_owner_async",
        "get_assignment_history": "get_assignment_history_async",
        "read_tasks": "read_tasks_async",
        "save_task": "save_task_async",
        "update_task_status": "update_task_status_async",
    },
    "team_service": {
        "create_team": "acreate_team",
        "find_team_by_code": "afind_team_by_code",
        "get_team": "aget_team",
        "get_member_role": "aget_member_role",
        "is_member": "ais_member",
        "can_edit": "acan_edit",
        "join_team_by_code": "ajoin_team_by_code",
        "get_user_teams": "aget_user_teams",
        "get_team_members": "aget_team_members",
        "leave_team": "aleave_team",
        "regenerate_codes": "aregenerate_codes",
    },
}


def offset(text: str, line: int, col: int) -> int:
    lines = text.splitlines(keepends=True)
    return sum(map(len, lines[: line - 1])) + col


def enclosing_function(tree: ast.AST, node: ast.AST):
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return None


def is_awaited(tree: ast.AST, node: ast.Call) -> bool:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return isinstance(parents.get(node), ast.Await)


def imported_service_names(tree: ast.Module):
    imported: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module not in MAPPINGS:
            continue
        mapping = MAPPINGS[node.module]
        for alias in node.names:
            if alias.name in mapping:
                imported[alias.asname or alias.name] = mapping[alias.name]
    return imported


def rewrite_imports(text: str, tree: ast.Module) -> str:
    replacements: list[tuple[int, int, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module not in MAPPINGS:
            continue
        mapping = MAPPINGS[node.module]
        for alias in node.names:
            if alias.name in mapping and alias.asname is None:
                start = offset(text, alias.lineno, alias.col_offset)
                end = offset(text, alias.end_lineno, alias.end_col_offset)
                replacements.append((start, end, mapping[alias.name]))
    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    return text


def transform(text: str) -> tuple[str, bool]:
    tree = ast.parse(text)
    imported = imported_service_names(tree)
    async_names = set(imported.values())

    # Discover functions that must become async. Propagate through local call sites
    # until every caller on the handler path is async.
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    local_names = {f.name: f for f in funcs}
    needs_async: set[str] = {f.name for f in funcs if isinstance(f, ast.AsyncFunctionDef)}

    changed = True
    while changed:
        changed = False
        for f in funcs:
            if f.name in needs_async:
                continue
            for call in [n for n in ast.walk(f) if isinstance(n, ast.Call)]:
                name = call.func.id if isinstance(call.func, ast.Name) else None
                if name in async_names or name in needs_async:
                    needs_async.add(f.name)
                    changed = True
                    break

    edits: list[tuple[int, int, str]] = []

    # Add async to functions which were synchronous but are on the async DB path.
    for f in funcs:
        if f.name not in needs_async or isinstance(f, ast.AsyncFunctionDef):
            continue
        start = offset(text, f.lineno, f.col_offset)
        edits.append((start, start, "async "))

    # Await imported async service calls and calls to functions made async above.
    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        name = call.func.id if isinstance(call.func, ast.Name) else None
        if not name:
            continue
        if name not in async_names and name not in needs_async:
            continue
        func = enclosing_function(tree, call)
        if not func:
            continue
        if func.name not in needs_async and not isinstance(func, ast.AsyncFunctionDef):
            continue
        if is_awaited(tree, call):
            continue
        start = offset(text, call.lineno, call.col_offset)
        edits.append((start, start, "await "))

    if not edits:
        return text, False

    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]

    # Reparse after structural edits, then update imported service names.
    tree2 = ast.parse(text)
    text2 = rewrite_imports(text, tree2)
    return text2, text2 != text


def main() -> None:
    changed_files = []
    for path in TARGETS:
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        try:
            transformed, changed = transform(original)
        except SyntaxError as exc:
            raise SystemExit(f"Cannot parse {path}: {exc}") from exc
        if changed:
            ast.parse(transformed)
            path.write_text(transformed, encoding="utf-8")
            changed_files.append(str(path.relative_to(ROOT)))
    print("Asyncified files:")
    for item in changed_files:
        print(f" - {item}")


if __name__ == "__main__":
    main()
