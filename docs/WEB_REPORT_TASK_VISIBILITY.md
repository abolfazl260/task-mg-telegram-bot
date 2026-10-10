# Web Reports: Core Task Visibility Contract

The standard TaskMG **Web Reports** page and its CSV/PDF exports use the same
task population as the Core `get_all_user_tasks_async(user_id)` list:

- **Personal ("my tasks")**: general tasks in `workspace_id IS NULL`, with
  no `team_id`, created by the requesting user (`tasks.user_id`).
- **Team tasks**: any general task attached to a team where the requesting
  user **currently** has a row in `team_members` (owner, editor, or viewer).
  Membership, not `assignee_id` or author identity alone, grants visibility.
  Leave/removal immediately stops report and event visibility.
- **Assigned to me**: an operational attribute/filter, **not** an independent
  authorization grant. A task assigned to a user, but owned by another user
  outside any shared team, is not part of their reports.
- **Created by me**: a reporting/filter concept. A task created by a user
  inside a team is not visible when the user no longer belongs to that team.
- **Bot Profiles**: Core general tasks are intentionally shared user data;
  `bot_key` is provenance/configuration, not a read permission. The signed,
  bearer Web Report token identifies the requesting user, but does not restrict
  this shared Task population to one bot's `bot_key`.
- **Clinic/workspace data**: Tasks with `workspace_id IS NOT NULL` are
  **excluded**, even when the current user is an owner or assignee.
  Workspace-sensitive reports require a separate, authorized scope contract.

The predicate is enforced inside SQL in `webapp.reports._task_scope()` and
reused by report summary rows, previous-period counts, recent events and
activity feed; export routes call the same dashboard service. All SQL
parameters use bind variables. There is no fallback to fetching all tasks and
filtering in Python. Repeated team member rows cannot duplicate task rows
because visibility uses `EXISTS`.

The `habits` reporting section remains separately scoped by owner **and Bot
Profile** under Issue #219; Habits should not inherit the shared-task policy.

## Deliberately out of scope

Issue #222 establishes *who may appear in reports*. It does not change the
time period's definition, overdue KPI meaning, date-span limits or the
permissions of task-edit endpoints. Report tokens remain bearer credentials;
their issuance/revocation and write capabilities are separate security topics.
