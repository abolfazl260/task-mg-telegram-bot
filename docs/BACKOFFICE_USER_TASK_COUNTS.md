# Back Office User Task Counts and Drill-Down

## Purpose

The existing User Management page already provided a user list and a basic
task count. This change makes that count reliable with a bot filter and makes
the meaning of **tasks for a user** explicit.

## Numbers and views

- **Created** / `task_count`: number of generic personal/team tasks with
  `tasks.user_id = users.user_id`.
- **Assigned** / `assigned_task_count`: number of generic personal/team tasks
  with `tasks.assignee_id = users.user_id` (current assignee).
- A task created by and assigned to the same person is counted once in
  **each independent column**, not as two unique tasks. Do not sum the columns
  to derive a unique-task count.
- All task statuses (including done/cancelled and archived) are counted,
  reflecting the stored task history rather than an active backlog KPI.
- A selected `bot_key` limits both counts and drill-downs to that bot. A
  user is listed under that bot when they either created or are assigned one
  of its generic tasks. The global unfiltered list includes users with zero
  tasks; the database has no authoritative user-to-bot membership registry,
  so a selected bot cannot show users with zero task association.
- **Clinic/workspace patient, session, clinical and other workspace tasks are
  deliberately excluded** (`workspace_id IS NULL`) from both views. The
  generic administrator panel is not a substitute for Clinic role-scoped
  patient access or bulk medical-data exports.

## API

All endpoints are authenticated by the existing admin session.

- `GET /api/admin/users?bot_key=&search=&limit=50&offset=0` responds with
  `total`, `limit`, `offset` and users including `task_count` and
  `assigned_task_count`.
- `GET /api/admin/users/{id}?bot_key=` returns the same count fields for
  a particular visible user, alongside profile metadata.
- `GET /api/admin/users/{id}/tasks?bot_key=&view=created|assigned&limit=25&offset=0`
  returns `tasks`, `total`, `limit`, `offset`, `view`, `user_id`.
  `view` defaults to `created` for backwards compatibility. Page size is
  bounded to 1–100 and offset is nonnegative, so a single HTTP request
  cannot materialize the entire task archive.
- Recent Users on the dashboard receive matching counts.

## Testing / risk boundaries

Tests exercise creator-only and assigned-only users, self-assignment, two
bot profiles, search+bot parameter binding, empty results, the 25/39-row
page break, count consistency, and clinic exclusion. Static UI assertions
cover the two-column list and drill-down selector.

Back Office remains **read-only** for these views and does not alter task
authorization, the TaskBot list, workspace permissions or any existing
clinic-facing endpoint.
