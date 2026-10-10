# Web Report KPI population and date contract (Issue #225)

All Web Report queries and exports use the same **Core task visibility**
predicate as the task list: personal records owned by the viewer and team
records in teams they currently belong to. Bot Profile provenance does not
restrict Core tasks; workspace/Clinic tasks, other users' private work and
revoked team memberships are excluded. See
[WEB_REPORT_TASK_VISIBILITY.md](WEB_REPORT_TASK_VISIBILITY.md).

## Three independent populations

1. **Created in selected period (UTC):** `summary.total`, `done`,
   `in_progress`, `pending`, `cancelled`, `active`, `with_deadline`,
   `completion_rate`, by-status/priority/category, lead/cycle time,
   task tables, and exports' task rows. A task created during the period
   is assessed by its **current** status; this is not an historical
   status snapshot. The existing comparison with the previous reporting
   period counts tasks **created** in each period. These fields retain
   their original API meanings.

2. **Completed in selected period (UTC):** `summary.completed_in_period`
   counts tasks currently marked `done` or `completed` whose
   `completed_at` is a parseable timestamp in the selected inclusive UTC
   calendar interval. This may include tasks created before the interval.
   `completed_with_deadline` is the subset with a **valid** ISO
   calendar deadline. `completed_on_time` and `completed_late` partition
   these eligible completions by comparing the UTC completion **date** to
   the stored deadline's calendar date (a same-day completion is on-time).
   `on_time_rate = completed_on_time / completed_with_deadline * 100`;
   `overdue_rate = completed_late / completed_with_deadline * 100`.
   These *completion* rates do **not** measure the share of all tasks
   currently overdue. A completed task without a valid completion timestamp
   or due date is excluded from the rate's denominator. When eligible
   completions are zero, both rates are JSON **null** and the UI/export
   displays **—**, never 100% or 0%. Offsets in `completed_at` are
   normalized to UTC before determining its calendar date.

3. **Currently open deadline backlog (as of UTC today):**
   `summary.overdue` and `summary.productivity.open_overdue` count all
   authorized **currently open** tasks with a deadline date strictly
   *before today*, regardless of their creation reporting period.
   `productivity.open_on_track` includes open tasks due **today or later**.
   Completed or cancelled statuses do not contribute; future-created records
   are not counted. `summary.backlog_as_of_utc` gives the snapshot date.
   These values are based on *current* status and due date, not reconstructed
   historical state. They use SQL `SUM(CASE WHEN ...)` and do not load
   all historical tasks into report memory.

## Filters and exports

The same token-based Core authorization and free-text/structured
search filters are applied to each population. A restrictive `status`
filter can make the open backlog zero (for example `done`), or the
completed-rate denominator zero (for example `pending`). The
`overdue` filter also acts on **current** overdue status; it does not
mean 'was once overdue at the historical reporting period's end'.

CSV and PDF retain the created-cohort task rows and now label the
created-cohort summary alongside the completed-period punctuality rates
and live open backlog **with its snapshot date**. No older overdue task
is inserted into the selected-period task table or exported task rows merely
because it contributes to the backlog total.

## Caveats and deferred work

- This is a current-status view, not historical event sourcing. A task
  subsequently reopened or deleted may change a past-period report. True
  'open backlog as of September 30' requires immutable state transitions,
  which are outside this issue.
- Empty/invalid `completed_at` is not proof of punctual completion and
  must not be counted as on-time.
- Deadline strings are treated as *calendar due dates* (first ISO date
  component), not timezone-shifted instant deadlines. Completion instants
  are normalized to UTC for period inclusion and comparison. This matches
  the existing date-picker's due-date-oriented task fields.
- `summary.done` remains the current completed state of **created-period**
  tasks for compatibility. Do not substitute it for
  `summary.completed_in_period` when displaying completion throughput.
