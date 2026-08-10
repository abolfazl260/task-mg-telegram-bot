from __future__ import annotations

import ast
import pathlib

TARGETS = {
    "create_task": "create_task_async",
    "get_active_tasks": "get_active_tasks_async",
    "get_task_by_id": "get_task_by_id_async",
    "change_task_status": "change_task_status_async",
    "user_can_modify_task": "user_can_modify_task_async",
    "assign_task": "assign_task_async",
    "get_unassigned_tasks": "get_unassigned_tasks_async",
    "add_task_comment": "add_task_comment_async",
    "get_task_comments": "get_task_comments_async",
    "get_user_teams": "aget_user_teams",
    "get_team_members": "aget_team_members",
}


def is_awaited(node: ast.AST) -> bool:
    parent = getattr(node, "_parent", None)
    return isinstance(parent, ast.Await)


def asyncify(path: str) -> None:
    file = pathlib.Path(path)
    tree = ast.parse(file.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    async_names = {
        name for name, node in functions.items() if isinstance(node, ast.AsyncFunctionDef)
    }

    # Propagate async upward through local helper calls and direct service calls.
    changed = True
    while changed:
        changed = False
        for name, node in functions.items():
            if name in async_names:
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Name):
                    continue
                if child.func.id in TARGETS or child.func.id in async_names:
                    async_names.add(name)
                    changed = True
                    break

    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node

    class Transformer(ast.NodeTransformer):
        def __init__(self):
            self.function_stack: list[str] = []

        def _convert_function(self, node):
            if node.name in async_names and isinstance(node, ast.FunctionDef):
                converted = ast.AsyncFunctionDef(
                    name=node.name,
                    args=node.args,
                    body=node.body,
                    decorator_list=node.decorator_list,
                    returns=node.returns,
                    type_comment=node.type_comment,
                )
                if hasattr(node, "type_params"):
                    converted.type_params = node.type_params
                ast.copy_location(converted, node)
                node = converted
            self.function_stack.append(node.name)
            node = self.generic_visit(node)
            self.function_stack.pop()
            return node

        def visit_FunctionDef(self, node):
            return self._convert_function(node)

        def visit_AsyncFunctionDef(self, node):
            return self._convert_function(node)

        def visit_Name(self, node):
            if node.id in TARGETS:
                node.id = TARGETS[node.id]
            return node

        def visit_Call(self, node):
            node = self.generic_visit(node)
            if not self.function_stack:
                return node
            fname = node.func.id if isinstance(node.func, ast.Name) else None
            should_await = fname in set(TARGETS.values()) or fname in async_names
            if should_await and not is_awaited(node):
                return ast.copy_location(ast.Await(value=node), node)
            return node

    tree = Transformer().visit(tree)
    ast.fix_missing_locations(tree)

    # Ensure imported public names are replaced with their canonical async names.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {
            "services.task_service",
            "services.team_service",
        }:
            for alias in node.names:
                if alias.name in TARGETS:
                    alias.name = TARGETS[alias.name]
                    alias.asname = None

    file.write_text(ast.unparse(tree) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncify("handlers/task.py")
    asyncify("handlers/team.py")
