# کاتالوگ قابلیت‌ها — Healthcare Clinics Feature Catalog

> وضعیت سند: Product Strategy v1  
> Vertical: Healthcare Clinics  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> اصل محصول: **System of Record را جایگزین نکن؛ System of Action را بساز.**

---

# 1. هدف این سند

این سند مرجع تصمیم‌گیری برای قابلیت‌های Vertical کلینیک است و باید بین چهار وضعیت تفاوت بگذارد:

- **Core موجود**: قابلیت در هسته TaskMG وجود دارد و عمدتاً قابل reuse است.
- **موجود ولی غیرفعال/نیازمند پیکربندی**: قابلیت در پروژه هست اما در Bot Profile کلینیک فعلی فعال نیست یا UX اختصاصی کلینیک ندارد.
- **Vertical Gap**: برای Product-Market Fit کلینیک نیاز است و باید توسعه داده شود.
- **Later**: قابلیت مفید است اما برای MVP ضروری نیست.

این کاتالوگ Feature Wishlist نیست. هر قابلیت باید به یک JTBD، Persona، Workflow و Outcome متصل باشد.

---

# 2. وضعیت پایه فعلی

طبق Feature Matrix پروژه، هسته فعلی TaskMG قابلیت‌هایی مانند موارد زیر را دارد:

- Task Management
- Teams
- Assignment
- Comments
- Attachments
- Tags
- Categories
- Priority
- Deadline
- Reminders
- Search
- Reports
- AI
- Voice
- Templates
- Bulk Import
- Integrations
- Export

اما در Bot Profile فعلی کلینیک، بعضی قابلیت‌ها از جمله Templates، Integrations و AI غیرفعال‌اند. بنابراین «وجود در هسته» به معنی «آماده بودن برای Vertical کلینیک» نیست.

---

# 3. اصول اولویت‌بندی Feature

هر Feature با این معیارها ارزیابی شود:

1. شدت Pain
2. دفعات استفاده
3. نقش در Workflowهای P0
4. اثر بر Adoption
5. اثر بر Management Visibility
6. هزینه پیاده‌سازی
7. ریسک امنیت/حریم خصوصی
8. امکان reuse از Core
9. نیاز به Integration
10. قابلیت اندازه‌گیری Outcome

اولویت‌ها:

- **P0** — لازم برای MVP/Pilot
- **P1** — Early Product
- **P2** — Scale
- **P3** — Later / Optional

---

# 4. Patient / Client Management

## هدف

Patient object در TaskMG Healthcare باید **Patient Record رسمی و قابل توسعه** باشد. اطلاعات هویتی، ارتباطی و clinical data می‌توانند در خود TaskMG ذخیره شوند و برای هر بخش permission، audit و lifecycle مناسب اعمال شود.

## P0

### Patient Record
حداقل فیلدها:
- internal ID
- display name
- optional phone/contact reference
- branch
- primary doctor
- operational tags
- active/inactive status

### Patient Search
جستجو بر اساس:
- نام
- شناسه
- شماره تماس در صورت مجاز بودن
- tag
- doctor
- branch

### Patient Activity View
فقط فعالیت عملیاتی:
- open tasks
- follow-ups
- cases
- comments
- recent activity

### Patient Next Action
نمایش:
- next action
- owner
- due
- status

## P1

- duplicate detection
- merge duplicate records
- custom operational fields
- patient-level timeline
- import from PMS

## P2

- patient communication preferences
- consent metadata
- cross-branch patient reference

## Out of Scope

Patient Record scope شامل این دسته‌ها نیز می‌شود و باید به‌صورت ماژولار توسعه یابد:
- clinical chart / clinical notes
- diagnosis history
- medication history
- allergies / chronic conditions
- treatment-related information
- medical documents / attachments
- imaging metadata و در صورت تصمیم محصول، imaging storage/integration

---

# 5. Task Management

## وضعیت

**Core موجود — نیازمند Vertical UX**

## P0

- create task
- assign owner
- due date/time
- priority
- status
- completion
- cancellation
- restore/reopen
- patient/case context
- outcome
- next action
- blocker reason

## Required Statuses

- New
- Assigned
- In Progress
- Waiting
- Blocked
- Completed
- Cancelled

## Product Rule

Task مهم نباید بدون owner یا due باقی بماند، مگر workflow صراحتاً اجازه دهد.

## P1

- dependencies
- SLA
- escalation level
- batch actions
- recurring generation
- task source tracking

## P2

- cross-branch assignment
- workload balancing
- auto-routing by role

---

# 6. Team & Roles

## وضعیت

**Core موجود — نیازمند RBAC اختصاصی کلینیک**

## P0 Roles

- Owner
- Clinic Manager
- Doctor / Dentist
- Reception
- Coordinator
- Assistant
- Admin

## P0 Capabilities

- invite/add staff
- role assignment
- role-based queue
- scope by branch
- assignment permission
- report permission
- patient/case visibility

## P1

- custom roles
- temporary access
- shift-based visibility
- role delegation

## P2

- regional manager
- multi-branch hierarchy
- central operations role

---

# 7. Appointment Follow-up

## اصل

TaskMG در MVP نباید full scheduling engine باشد.

## P0

- appointment reference
- appointment date/time
- linked patient
- linked doctor
- follow-up task after cancellation/no-show
- pre-appointment operational task

## P1

- calendar sync
- no-show event trigger
- rebooking outcome
- reminder integration

## P2

- deeper PMS appointment sync
- cross-location appointment actions

## Not Now

- replacing full practice calendar
- complex chair/resource scheduling

---

# 8. Reminder

## وضعیت

**Core موجود — نیازمند workflow-aware behavior**

## P0

- task reminder
- due-soon reminder
- overdue reminder
- follow-up reminder
- configurable lead time

## P1

- escalation reminder
- digest notifications
- quiet hours
- reminder by role

## P2

- patient-facing reminder through approved channel
- smart reminder timing

---

# 9. Treatment Workflow

## وضعیت

**Vertical Gap کلیدی**

Treatment Workflow در TaskMG باید operational باشد، نه clinical.

## P0

### Case
یک container برای workflow چندمرحله‌ای.

### Case State
- Active
- Waiting
- Blocked
- Completed
- Closed

### Case Next Action
هر case فعال باید ترجیحاً next action داشته باشد.

### Workflow Template
مراحل استاندارد برای:
- Treatment Plan Follow-up
- Lab Case
- Post-Treatment Follow-up
- Daily Operations

## P1

- multi-step case
- dependencies
- stage transition rules
- required outcome
- stage-level SLA
- automated next task

## P2

- branching workflows
- cross-branch case
- complex orchestration

---

# 10. Follow-up Queue

## وضعیت

**Vertical Gap / P0**

یکی از مهم‌ترین differentiatorها.

## قابلیت‌ها

- due today
- overdue
- upcoming
- no answer
- rescheduled
- by owner
- by doctor
- by branch
- by workflow

## Outcomeهای پایه

- Reached
- No Answer
- Scheduled
- Needs Time
- Declined
- Escalated
- Closed

## Metric

- follow-up completion rate
- median delay
- no-next-action rate

---

# 11. Comments & Internal Notes

## وضعیت

**Core موجود**

## P0

- task comments
- case comments
- mentions
- timestamp
- author
- internal-only context

## P1

- structured note type
- pinned note
- resolution note

## Rule

Internal notes نباید به patient-facing channel نشت کنند.

---

# 12. Tags & Categories

## وضعیت

**Core موجود**

## P0

### Tags
- VIP
- high-value
- lab
- recall
- urgent
- follow-up

### Categories
- Callback
- Lab
- Complaint
- Post-Treatment
- Internal Ops

## P1

- admin-controlled vocabulary
- branch-specific tags
- tag automation

## Rule

از tag برای جایگزینی structured fields استفاده نشود.

---

# 13. Search & Filters

## وضعیت

**Core موجود — Vertical filters لازم**

## P0 Filters

- patient
- owner
- doctor
- status
- due
- overdue
- workflow
- branch
- category
- tag

## P1

- saved views
- shared views
- advanced compound filter

## P2

- semantic search
- AI-assisted query

---

# 14. Templates

## وضعیت

Core قابلیت Template دارد، اما در Bot Profile فعلی clinic غیرفعال است.

## P0

MVP Template Pack:

1. Treatment Plan Follow-up
2. General Callback
3. Lab Case
4. Post-Treatment Follow-up
5. Daily Clinic Checklist

## P1

- editable template
- role defaults
- default due rules
- outcome configuration
- escalation rules

## P2

- template marketplace/library
- versioning
- rollout across branches

---

# 15. Recurring Tasks

## P0

- daily opening checklist
- daily closing checklist
- recurring management review

## P1

- weekly/monthly tasks
- recurrence exceptions
- pause/resume

## P2

- branch-level recurring templates

---

# 16. Dashboard & Reports

## وضعیت

**Core Reports موجود — Vertical metrics لازم**

## P0 Manager Dashboard

- open tasks
- overdue
- due today
- unassigned
- blocked
- follow-up queue
- cases without next action
- workload by staff

## P0 Owner Dashboard

- overdue trend
- completion trend
- workflow volume
- follow-up completion
- adoption

## P1

- cycle time
- workflow bottleneck
- outcome distribution
- staff workload trend
- branch comparison

## P2

- benchmark
- forecast
- anomaly detection

## Anti-pattern

Dashboard نباید صرفاً vanity metrics نمایش دهد.

---

# 17. Notifications

## P0

- assigned
- due soon
- overdue
- escalated
- blocked
- mention

## P1

- digest
- priority-aware
- quiet hours
- per-role preference

## P2

- adaptive notification policy

## Principle

**Exceptions over noise.**

---

# 18. File & Media Attachments

## وضعیت

**Core موجود**

## P0

- image
- document
- audio
- task attachment
- case attachment

## Security Requirements

- authorization check
- file size/type limit
- retention policy
- secure storage
- download audit where necessary

## Boundary

TaskMG نباید PACS یا imaging archive شود.

---

# 19. Voice Input

## وضعیت

**Core موجود/قابل reuse**

## P0

### Voice-to-Task
مثال:
«فردا ساعت ۱۰ با بیمار احمدی تماس بگیر.»

→ draft:
- title
- due
- patient candidate
- owner candidate

## P1

- voice outcome update
- voice reassignment
- voice follow-up scheduling

## Rule

AI-parsed action قبل از اجرای حساس باید confirmation داشته باشد.

---

# 20. AI Assistant

## وضعیت

Core AI موجود است اما در clinic profile فعلی غیرفعال است.

## P0

- natural-language task creation
- daily summary
- overdue summary
- safe operational Q&A

## P1

- next action suggestion
- workflow suggestion
- manager brief
- duplicate/forgotten action detection

## P2

- cross-workflow insight
- advanced prioritization

## Forbidden Scope

- autonomous diagnosis by AI
- autonomous treatment recommendation
- medication recommendation
- autonomous clinical action

---

# 21. Integrations

## وضعیت

Integration infrastructure در Core وجود دارد، اما clinic profile فعلی غیرفعال است.

## P0

- CSV import/export
- basic API/webhook foundation
- Telegram

## P1

- Google Calendar
- Microsoft Outlook Calendar
- existing clinic software via API/export
- email
- SMS/WhatsApp provider abstraction

## P2

- PMS-specific connectors
- payment
- accounting
- lab systems
- FHIR-compatible integration where justified

## Rule

Integration باید duplicate entry را کم کند یا trigger/outcome مهم بسازد.

---

# 22. Export

## وضعیت

Core export/report export موجود.

## P0

- CSV
- report export

## P1

- PDF management report
- filtered export
- audit export

## P2

- scheduled export
- data warehouse connector

---

# 23. Multi-Branch

## P2 / Scale

### Objects
- Organization
- Branch
- Branch Membership
- Branch Role

### Capabilities
- branch-scoped data
- central templates
- branch dashboards
- central reporting
- cross-branch permissions
- branch comparison

## Prerequisite

tenant isolation و RBAC باید قبل از scale تثبیت شوند.

---

# 24. Audit & Activity Log

## P0

برای حوزه حساس کلینیک، audit feature فرعی نیست.

حداقل Eventها:

- task created
- assigned
- reassigned
- due changed
- status changed
- outcome changed
- patient/case linked
- comment added
- attachment added
- export
- permission change

## P1

- admin audit viewer
- filters
- actor/IP/device metadata where appropriate

## P2

- compliance export
- anomaly alert

---

# 25. Security Features

## P0

- authentication
- role-based access
- tenant isolation
- branch scope
- authorization on every read/write
- audit
- safe error messages
- secure secrets handling

## P1

- MFA where applicable
- session management
- data retention controls
- configurable export permission
- integration scopes

## P2

- enterprise SSO
- advanced audit
- policy enforcement

---

# 26. Feature Dependency Map

### Patient Follow-up
Patient Record  
→ Task  
→ Owner  
→ Due  
→ Outcome  
→ Next Action  
→ Reminder  
→ Dashboard

### Case Workflow
Patient Record  
→ Case  
→ Workflow Template  
→ Task  
→ Dependency  
→ Outcome  
→ Next Stage  
→ Report

### Multi-Branch
Organization  
→ Branch  
→ Membership  
→ RBAC  
→ Branch Scope  
→ Central Reporting

---

# 27. Feature Priority Matrix

| Feature | Priority | Core Reuse | Vertical Work | Main Persona |
|---|---|---:|---:|---|
| Task | P0 | High | Medium | All |
| Assignment | P0 | High | Medium | Manager |
| Due/Reminder | P0 | High | Medium | Frontline |
| Patient Record | P0 | Low | High | Reception |
| Follow-up Queue | P0 | Medium | High | Coordinator |
| Case | P0/P1 | Low | High | Manager |
| Outcome | P0 | Low | High | Coordinator |
| Next Action | P0 | Low | High | Manager |
| Templates | P0 | Medium | High | Manager |
| Dashboard | P0 | High | High | Manager |
| Audit | P0 | Medium | High | Owner/Admin |
| Voice | P1 | High | Medium | Doctor/Reception |
| AI Summary | P1 | High | Medium | Manager |
| Calendar Sync | P1 | Medium | High | Reception |
| PMS Sync | P1/P2 | Medium | High | Clinic |
| Multi-Branch | P2 | Medium | High | Ops Manager |

---

# 28. MVP Feature Pack

برای MVP فقط این مجموعه باید end-to-end قابل اعتماد باشد:

1. Clinic / staff setup
2. Roles & permissions
3. Patient Record
4. Task + owner + due
5. Follow-up queue
6. Outcome
7. Next Action
8. Reminder
9. Five workflow templates
10. Comments
11. Search/filter
12. Manager dashboard
13. Audit log
14. Telegram execution
15. Web management
16. CSV import/export

---

# 29. ویژگی‌هایی که عمداً MVP نیستند

- autonomous clinical decision support بدون guardrail/approval
- billing/insurance در صورت نبود تصمیم محصول مستقل
- insurance
- patient portal
- full CRM
- inventory ERP
- advanced multi-branch
- complex workflow designer
- autonomous AI
- clinical decision support

---

# 30. Feature Acceptance Rule

هیچ Feature وارد Roadmap نشود مگر اینکه حداقل این موارد مشخص باشند:

- JTBD
- Persona
- Trigger
- Expected Outcome
- Data Required
- Permission Model
- Metric
- Failure Mode
- MVP/Next/Later status

---

# 31. Definition of Product Completeness

Vertical زمانی «Feature Complete برای Pilot» است که پنج Workflow P0 بدون workaround خارج از سیستم قابل اجرا باشند و manager بتواند از Dashboard همان workflowها را monitor کند.

Feature Count معیار موفقیت نیست؛ **Workflow Completion** معیار است.
