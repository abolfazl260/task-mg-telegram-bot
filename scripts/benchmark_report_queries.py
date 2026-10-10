"""Synthetic, dependency-free microbenchmark for the report period-count query.

Run: python scripts/benchmark_report_queries.py
This uses an isolated in-memory SQLite database, never production data.
"""
from __future__ import annotations

import sqlite3
import statistics
import time


def benchmark(size: int) -> tuple[int, float, float, str]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE tasks (
          id TEXT PRIMARY KEY, bot_key TEXT, user_id TEXT,
          workspace_id TEXT, created_at TEXT, title TEXT,
          category TEXT, priority TEXT, status TEXT, assignee_name TEXT,
          deadline TEXT, completed_at TEXT
        );
        CREATE INDEX idx_tasks_bot_user ON tasks(bot_key, user_id);
        CREATE INDEX idx_tasks_report_created ON tasks(bot_key, user_id, created_at);
        """
    )
    rows = [
        (
            f"task-{i}", "bot", "42", None,
            f"2026-{'09' if i % 2 == 0 else '10'}-{i % 28 + 1:02d}T09:00:00Z",
            "A test item", "work", "medium", "pending", "", "", "",
        )
        for i in range(size)
    ]
    connection.executemany(
        "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    where = (
        "workspace_id IS NULL AND bot_key=? AND user_id=? "
        "AND created_at>=? AND created_at<?"
    )
    arguments = ("bot", "42", "2026-09-01", "2026-10-01")

    def median_ms(sql: str) -> float:
        samples = []
        for _ in range(11):
            started = time.perf_counter()
            connection.execute(sql, arguments).fetchall()
            samples.append((time.perf_counter() - started) * 1000)
        return statistics.median(samples)

    full_sql = "SELECT * FROM tasks WHERE " + where
    count_sql = "SELECT COUNT(*) AS total FROM tasks WHERE " + where
    full_ms = median_ms(full_sql)
    count_ms = median_ms(count_sql)
    plan = connection.execute("EXPLAIN QUERY PLAN " + count_sql, arguments).fetchone()[3]
    count = connection.execute(count_sql, arguments).fetchone()["total"]
    connection.close()
    return count, full_ms, count_ms, plan


if __name__ == "__main__":
    for number_of_tasks in (100, 1_000, 10_000):
        count, fetch_ms, scalar_ms, query_plan = benchmark(number_of_tasks)
        print(
            f"tasks={number_of_tasks:>6} previous={count:>5} "
            f"full_fetch_ms={fetch_ms:>8.3f} sql_count_ms={scalar_ms:>8.3f} "
            f"speedup={fetch_ms / max(scalar_ms, 1e-9):.1f}x "
            f"plan={query_plan}"
        )
