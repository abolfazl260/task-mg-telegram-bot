# Clinic Vertical Architecture — Canonical Target

> Status: Target architecture and roadmap source of truth  
> Vertical: Healthcare / Clinic  
> Architecture rule: Core-first → Modular → Configurable → Feature-flagged → Vertical Profile

## 1. Product goal

A clinic must be able to use TaskMG as a **complete standalone clinic workspace** for its day-to-day patient and staff management. External PMS/EMR integration is optional, not required for normal use.

TaskMG Clinic must be able to store and manage the patient's persistent record, historical information, clinical information, sessions/visits, operational actions and follow-ups in its own database.

## 2. Core abstraction

Vertical-specific concepts must be built from generic Core primitives.

The primary Core abstraction is a **Typed Work Item / Record**:

- item type
- parent item
- child items
- status/lifecycle
- owner/assignee
- branch/workspace
- attribute schema
- permissions
- attachments
- activity/history
- searchable/indexed attributes
- views/forms/layouts
- report definitions

The existing Task concept should evolve without breaking generic TaskBot behavior.

## 3. Clinic mapping

Clinic is a Vertical Profile over Core.

Recommended mapping:

- Patient = top-level typed Work Item / Task
- Session / Visit = child Work Item / Subtask
- Follow-up = child Work Item / Subtask or typed action
- Treatment Case = optional typed child item when needed
- Attachment/Document = related Core attachment
- Patient fields = Core Attribute values selected by Clinic schema

The database/core must not hard-code fields only because they belong to Clinic. Field types and storage/indexing are Core capabilities; Clinic chooses and configures the schema.

## 4. Core Attribute Schema

Core must support reusable field definitions such as:

- short text
- long text
- phone
- email
- integer/decimal/money
- date
- datetime
- boolean
- enum
- multi-select
- user reference
- work-item reference
- attachment/document
- repeatable/multi-value field

Each field definition must support:

- key
- label
- type
- required/optional
- repeatable
- validation
- default
- searchable
- filterable
- sortable where applicable
- sensitive flag
- role visibility/editability
- section/group
- display order
- vertical/profile activation

## 5. Patient Record

Clinic must configure a Patient item with a durable record that can include:

- first name
- last name
- full/display name
- patient/external ID
- date of birth
- gender where needed
- multiple mobile/phone numbers as separate repeatable values
- email/contact channels
- address where needed
- branch
- responsible doctor/dentist
- disease history
- chronic conditions
- allergies
- medications
- diagnoses
- clinical notes
- treatment-related information
- tags
- documents/images/attachments
- created/updated metadata
- patient activity history
- sessions/visits
- follow-ups/actions

Clinical data is part of the product and stored by TaskMG.

## 6. Session / Visit

A Session/Visit is a child item under the Patient.

Typical attributes:

- scheduled date/time
- actual start/end when needed
- doctor/dentist
- branch
- visit/session type
- status: scheduled / completed / cancelled / no-show / rescheduled
- reason/title
- notes
- clinical/session notes
- performed actions/procedures as configurable attributes
- next follow-up
- attachments
- created by / updated by

Past sessions remain in patient history.

## 7. Roles

Clinic roles are configured on top of Core permissions.

Minimum roles:

### Owner/Admin
Full configuration and access subject to sensitive-data policy.

### Manager
Clinic/branch management, reports and staff operations.

### Secretary / Reception
Must be able to manage day-to-day Clinic work from Telegram and Web:
- create/search/edit patients
- manage patient contact information
- create/reschedule/cancel sessions
- view session history as permitted
- manage follow-ups/actions
- assign work
- update status/notes
- see today's operational queues

### Doctor / Dentist
Must be able to:
- search/view permitted patients
- view patient record and history
- view/create/update sessions
- enter permitted clinical notes/data
- create/delegate actions/follow-ups
- see own schedule/work queues

### Assistant / Coordinator
Configured subset based on clinic policy.

## 8. Clinic Web Workspace

Clinic needs its **own vertical workspace**, not a generic Task dashboard with renamed labels.

Required navigation:

- Dashboard
- Patients
- Sessions / Visits
- Follow-ups
- Tasks / Actions
- Doctors / Staff
- Branches
- Reports
- Settings

Patient detail should support vertical-specific tabs/sections such as:

- Profile
- Contact
- Medical History
- Medications
- Allergies
- Diagnoses
- Clinical Notes
- Sessions
- Follow-ups / Tasks
- Files / Documents
- Activity

All labels/layouts must come from the Vertical Profile / schema where possible.

## 9. Clinic-specific Reports

The report/query engine belongs to Core. Clinic defines report schemas, labels and metrics.

Examples:

- total patients
- new patients
- active patients
- sessions today
- upcoming sessions
- completed sessions
- cancelled/no-show sessions
- follow-ups due/overdue
- patients with no next action
- sessions by doctor
- sessions by branch
- workload by secretary/doctor
- patient activity trend
- repeat visit/session trend

## 10. Search and filters

Core must index/query typed attributes so Clinic can search/filter by:

- patient name
- any phone number
- patient ID
- doctor
- branch
- session date/status/type
- tags
- configurable attributes

Sensitive fields must respect permission during search and result rendering.

## 11. Security and audit

- workspace/branch isolation
- backend-enforced permissions
- field/section-level visibility for sensitive data where needed
- audit sensitive reads/writes where configured
- history of attribute changes
- no sensitive-data leakage to logs/notifications/analytics
- attachments inherit parent scope
- feature/module disabled state enforced server-side

## 12. Independence from external systems

A clinic must be fully usable without PMS/EMR integration.

Integrations are optional for:
- importing/syncing data
- reducing duplicate entry
- interoperability

They are not the source of truth requirement for basic Clinic operation.

## 13. AI boundary

Storing clinical data is in scope.

Autonomous diagnosis, prescription or treatment recommendation is not automatically enabled by storing the data. Those require separate capability, permission, validation, governance and human approval.

## 14. Definition of success

A new clinic can:
1. create a clinic workspace and branches;
2. create staff and assign Secretary/Doctor roles;
3. create complete Patient records;
4. store multiple phone numbers and medical/clinical history;
5. schedule and record Sessions/Visits;
6. see historical sessions under each patient;
7. manage the same data from Telegram according to role;
8. use a dedicated Clinic Web workspace;
9. use Clinic-specific reports;
10. operate without an external PMS/EMR.
