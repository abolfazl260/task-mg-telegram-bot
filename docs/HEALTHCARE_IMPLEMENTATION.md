# Healthcare operational domain

Implementation tracking: issues #112–#126. This module uses the existing SQLite
connection lifecycle, shared users, and `tasks` table. It does not represent a
medical record, clinical decision system, or appointment scheduler.

## Data and authorization

PatientReference → Case → existing Task / FollowUp → structured Outcome → next Task.

All new objects have an organization; patient-linked objects also have a branch.
Clinic memberships are independent of general team roles. Reception, coordinator,
and assistant memberships require a branch. Owner, manager and tenant admin may
have a branch or organization-wide membership. Doctor/dentist membership requires
a branch and queries additionally restrict records to the doctor relationship or
assigned action. A doctor's clinical context is independent of task ownership.
A global TaskMG admin ID does not bypass clinic membership.

`Scope` generates SQL restrictions used by both Telegram and Web. Caller-provided
roles are never trusted. Membership revocation takes effect on the next request.
Patient/case/task IDs are random identities, not access tokens. Foreign keys,
composite keys, and triggers reject inconsistent patient/case/task links and
cross-organization/branch assignments. Historical creator/owner references remain
valid after deactivation so another authorized staff member can close the work.

Legacy task list, report, export, reminder, integration and Telegram access paths
cannot read or modify new organization-linked tasks. Patient attachments are not
supported in this release; the generic attachment path cannot attach to a clinic
task. No public patient/case links exist.

## Migration and rollout

Startup adds nullable context columns to existing tasks, then creates clinic
objects, indexes and integrity triggers. Column additions serialize with `BEGIN
IMMEDIATE`; migration is repeatable. Existing task IDs, content, status and general
sharing behavior are preserved. Old tasks remain organization-unscoped; they are
not guessed into PatientReferences. An operator must explicitly map any legacy
patient-as-task data before using real clinic records with this profile.

Before upgrading an existing installation, take an operational database backup.
The migration is additive; reverting application code does not remove its tables
or columns. Do not drop the new schema while clinic tasks reference it.

`bots/clinic.json` enables `healthcare` and `clinic_staff_reminders`. Generic bots
have both flags disabled by default. Clinic commands expose `/clinic` and the
configured patient/case terminology. AI and external integrations remain disabled
for Clinic because clinic-specific authorization/confirmation and provider
mapping are not implemented. Enabling those existing generic features does not
make them authorized clinic actions.

Bootstrap an organization as an authenticated user with the clinic API, create a
branch, grant staff membership, create/import operational PatientReferences, then
create cases and follow-ups. This does not create, activate or configure Telegram
bot credentials.

## HTTP API

All routes use existing Telegram Web App authentication (`X-Telegram-Init-Data`)
and a configured active bot profile. Add `bot_key=clinic` and, except for scopes
and organization creation, `organization_id=<id>` to the query. The selected
organization must belong to that bot. Error responses are generic and do not echo
patient data, SQL details or search parameters.

| Method | Path after `/api/clinic` | Purpose |
|---|---|---|
| GET | `/scopes` | Actor's permitted clinic memberships |
| POST | `/organizations` | Bootstrap clinic and owner |
| GET / POST | `/branches` | Scoped branch list / create |
| POST | `/memberships` | Grant, change or deactivate membership |
| GET / POST | `/patients` | Paginated list / operational patient creation |
| GET / PATCH | `/patients/{id}` | Scoped read / edit / archive |
| GET / POST | `/cases` | Paginated list / case creation |
| GET / PATCH | `/cases/{id}` | Scoped read / status and blocker |
| GET | `/cases/{id}/timeline` | Related actions and outcomes |
| POST | `/cases/{id}/workflow` | Start a published version |
| POST | `/cases/{id}/stage` | Validated transition, with expected stage |
| GET / POST | `/tasks` | Scoped list / create case action |
| GET / PATCH | `/tasks/{id}` | Scoped read / execution status |
| POST | `/tasks/{id}/outcome` | Result independent of execution status |
| GET / POST | `/followups` | Paginated queue / create follow-up |
| GET | `/followups/{id}` | Scoped follow-up read |
| POST | `/followups/{id}/outcome` | Outcome and atomic successor |
| GET / POST | `/templates` | Latest definitions / publish immutable version |
| POST | `/templates/seed` | Idempotently install five configurable templates |
| GET | `/metrics` | Scoped operational facts and workload |
| POST | `/import/preview` | CSV row validation and duplicate preview |
| POST | `/import/confirm` | Revalidate and atomically import with confirmation |
| GET | `/export` | Permission-aware operational CSV |

Lists accept bounded `limit`/`offset` and applicable branch, owner, doctor, stage
and status filters. Patient lists accept `search`. Follow-up `view` accepts
`today`, `overdue`, `upcoming`, `no_answer`, `rescheduled`. Today/upcoming boundaries
use the organization's timezone, converted to UTC for indexed queries. An overdue
follow-up is any unfinished follow-up whose exact due timestamp has passed.
Case `missing_next_action=true` flags active cases with no usable pending action.

Timestamps in writes must be ISO 8601 with an explicit timezone. Storage and CSV
use ISO 8601 UTC. Phone/name and identifiers are validated for length; clinical
fields are not part of the domain DTO.

## Outcomes and workflow rules

`no_answer`, `scheduled`, `needs_time`, `escalated` and `rework` require a scheduled
next action. Terminal outcomes do not. Recording a follow-up result, completing
its execution task, creating the successor/attempt, and updating the case pointer
is one SQLite transaction. Overlapping retries with the same outcome return the
recorded result and never create another successor. Conflicting results fail.
Generic task outcomes do not change execution status.

Every template instance pins an immutable version. Editing a template publishes a
new version. Definitions validate stage keys, allowed transitions, owner roles,
due offsets and allowed outcomes. Transitions require the expected current stage
and completion of existing workflow actions. Five manual templates are included:
treatment plan follow-up, general callback, lab case tracking (including rework),
post-treatment follow-up, daily clinic checklist. Automatic recurrence, workflow
completion automation and configurable role escalation are **not** implemented.
Do not treat a seeded template as a complete recurring workflow product.

## Staff notifications

New timed tasks create durable staff notifications one hour before due (when
still upcoming), at due (when still upcoming), and one day overdue. Completion,
cancellation and case closure cancel pending notifications. Delivery claims use
an atomic SQLite update and prevent scheduler overlap across processes. Delivery
rechecks membership and task state; messages contain no patient name/contact or
clinical content. Bot and organization scopes are checked before claiming.

Telegram does not provide an idempotency key for sendMessage. A timeout can occur
after a message was accepted. Such failures are persisted for operator review and
are not automatically resent. A process crash after claim leaves `sending` for
review, rather than risking duplicate delivery. Explicit RetryAfter responses
retry at most three times. Manager escalation, quiet hours, a reconciliation UI,
and an operator retry procedure remain required before production pilot rollout.

## CSV, metrics, audit and retention

Patient CSV columns: `external_id,display_name,branch_id`, optional `phone,doctor_id`.
Input is UTF-8 (BOM accepted), bounded to 500 rows / 512 KB. Unknown/clinical
columns are rejected. Preview validates each row and branch mapping. Confirmation
revalidates source data. Organization-unique external IDs prevent duplicate
imports. Cross-branch duplicate conflicts fail generically. CSV tags and a
frontline import UI are not available yet.

Exports require `exports.create`, are capped at 5,000 rows, restrict fields and
neutralize spreadsheet formula prefixes. Names, contact details and narrative
text are omitted from operational exports. Supported kinds: tasks, followups,
cases, outcomes. Metrics expose counts, owner/due coverage, follow-up completion
rate and observed median delay in seconds (zero for early completion), overdue
counts, missing-next-action cases and workload. Empty rates/medians are null,
not fabricated zero performance. Historical PMF cohorts, baseline comparisons,
weekly active target users and time-to-first-value are not implemented.

Audit events have schema version 1 and contain tenant/branch, actor, action,
entity identity and UTC time. Database triggers prohibit audit update/delete.
Patient names, phones, free text and clinical content are excluded. Audit is
created in the same transaction as sensitive domain writes. Dashboard views and
exports are audited. Notifications use actor `system`.

Patient archiving preserves case/task/audit links and prevents new cases. There
is no default destructive retention job. A retention duration, identity erasure
policy and deployment-specific encryption/backup access policy must be agreed
before a real-data pilot. A permitted user can still read archived references;
archiving is operational lifecycle control, not erasure. Implement explicit
retention/anonymization before claiming issue #121 complete.

## Remaining rollout work

The Telegram module supports scoped queues, pagination, minimal patient/case
lists, outcome selection and explicit retry scheduling. It lacks inline patient
creation/search, a full role-specific checklist/delegation/approval flow and
arbitrary rescheduling. The authenticated API is ready for a Web workspace; this
PR does not build that full frontend. Calendar/PMS webhooks, integration mapping,
clinic AI/Voice drafts and confirmation/evaluation are intentionally deferred.

Tests use synthetic records. Domain and channel suites cover tenant/branch and
bot isolation, direct valid-ID denial, revocation, doctor context, five workflow
versions/transitions, outcome/next-action atomicity, queue timezone/pagination,
notification overlap/cancellation/failure, CSV duplicates, audit immutability,
metrics authorization and additive migration. They do not claim coverage of
unimplemented escalation, daily recurrence, integration or AI paths.
