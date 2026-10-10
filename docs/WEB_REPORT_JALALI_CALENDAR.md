# Web Report Jalali Heatmap and Due-Date Calendar (Issue #228)

## Two distinct calendar contracts

**Reporting filter:** the global `period=today|week|month|custom` controls
an **inclusive Gregorian (UTC)** date interval as documented in
`WEB_REPORT_INPUT_LIMITS.md`. The `month` preset is intentionally the
**Gregorian** current month. Switching how dates are *displayed* never
silently changes this reporting API contract.

**Heatmap navigation:** all dates are shown as Jalali dates and the
`previous/next solar month` buttons navigate **complete adjacent Jalali
months**, not Gregorian months. The API returns `navigation.calendar=jalali`,
`anchor_year`, `anchor_month`, `anchor_label`, and `current/previous/next`
Gregorian ISO `start/end` pairs derived from genuine Jalali boundaries.
The anchor is the Jalali month containing the **first date in the active
Heatmap request**, even if that request spans multiple months or was made
with the global Gregorian month preset. The Heatmap displays the **actual**
date interval separately to avoid representing partial months as full months.
Navigation uses `period=custom`, retains the active structured/search
filters and is disabled when the adjacent full month would exceed the
1900–2100 date envelope (#223). The global dashboard period selector is
not silently mutated by scrolling the Heatmap.

**Calendar section:** a seven-column, Saturday-first RTL date grid groups
every day in the selected interval by **Jalali month** or **Gregorian month**
depending on the view selector. Switching display mode preserves the same
underlying ISO dates, selected date, tasks and active filters. Buttons move
back/forward by **one whole month in the selected calendar system** and
retain filters while applying a custom date window. The user can select a
day to inspect **all** due tasks and their status, priority and assignee.
Mobile uses the same seven-column grid with compact cells, stacked
per-day details and keyboard-focusable date buttons.

## Calendar task data and permission semantics

The Calendar endpoint `/section/calendar` differs intentionally from the
legacy task list. Its population is all Core-authorized tasks with a **valid
deadline date in the chosen interval**; this includes tasks created in
earlier periods. It uses the same search/status/priority/assignee/current
overdue filters as other sections. A task without a valid deadline cannot
appear on a calendar date. The task creator date is *not* used as a filter.

The response retains `section`, `rows`, `total`, `page`, `pages`
and `page_size`, but **all** matching rows are returned (not an arbitrary
25-row slice) and `pagination_mode=none`, `page=1`, `pages=1`.
`days` is an inclusive, lightweight chronological index of every date,
Gregorian/Jalali labels, Saturday-first `weekday` and due-task count.
`range` is the actual ISO interval and `navigation.jalali/gregorian`
provides adjacent-month ISO bounds. `total` equals both `rows.length`
and the sum of the daily counts. The API's existing strict maximum
**366-day interval** is enforced independently by the report service
before any calendar expansion.

The membership-based Core visibility contract in
`WEB_REPORT_TASK_VISIBILITY.md` is unchanged: only the viewer's own
general personal tasks and general team tasks where the viewer currently
belongs. No access to unrelated private, removed-team, or workspace/Clinic
tasks. `bot_key` is provenance, not a Core task permission. Filtering is
performed in **parameterized SQL** under the Core predicate, without
fetching all users' tasks and filtering in Python.

## Performance and compatibility boundaries

The selected interval is bounded to at most 366 days; its day index is at
most 366 cells. A calendar day with **more than 25 events** returns all
items and shows the exact count. Extremely high task volume can still make
the JSON payload large because the contract intentionally has no hidden
row cap; server-side per-day lazy retrieval would require a separate
pagination API and explicit day-count consistency guarantees.

The regular `tasks` and `deadlines` tables remain paginated at 25 rows,
and full CSV/PDF exports continue to use created-period task rows.
The new Calendar does not change that export contract. Task deadlines are
calendar dates (first ISO `YYYY-MM-DD` portion), not timezone-shifted
instants. Report date boundaries are UTC; visual rendering is deterministic
on the server and does not depend on the client's local timezone.
