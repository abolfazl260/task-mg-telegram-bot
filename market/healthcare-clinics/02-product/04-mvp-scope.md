# محدوده MVP — Healthcare Clinics

> وضعیت سند: MVP Scope v1  
> Beachhead: کلینیک خصوصی دندان‌پزشکی چندپزشکه  
> هدف MVP: اثبات اینکه TaskMG می‌تواند workflowهای عملیاتی واقعی کلینیک را با Adoption قابل قبول و Outcome قابل اندازه‌گیری اجرا کند.

---

# 1. MVP چه چیزی را باید اثبات کند؟

MVP نباید اثبات کند که TaskMG یک نرم‌افزار جامع کلینیک است.

باید این فرضیه را اثبات کند:

**اگر یک کلینیک workflowهای follow-up و کارهای داخلی خود را با Owner، Due Date، Outcome و Next Action روی TaskMG اجرا کند، آیا missed action کمتر، visibility مدیر بیشتر و استفاده روزمره تیم پایدار می‌شود؟**

سه سؤال حیاتی:

1. آیا frontline واقعاً استفاده می‌کند؟
2. آیا manager واقعاً dashboard را برای تصمیم‌گیری استفاده می‌کند؟
3. آیا Buyer بعد از Pilot حاضر است برای ادامه استفاده پول بدهد؟

---

# 2. تعریف MVP

MVP یک **Clinic Operations Workflow Layer** است که در Telegram و Web اجرا می‌شود و پنج workflow پایه را پوشش می‌دهد:

1. Treatment Plan Follow-up
2. General Patient Callback
3. Lab Case Tracking
4. Post-Treatment Follow-up
5. Daily Clinic Checklist

---

# 3. Target User

## Primary Users

- Reception
- Patient Coordinator
- Clinic Manager
- Assistant

## Secondary Users

- Doctor / Dentist
- Owner

## Pilot Organization

بهترین Pilot:

- 2 تا 10 پزشک
- 5 تا 25 staff
- مدیر یا coordinator مشخص
- حداقل 5 کاربر روزانه
- follow-up واقعی روزانه
- willing champion
- حداکثر 1 تا 3 شعبه در فاز اولیه

---

# 4. Must Have — P0

## 4.1 Organization Setup

- Clinic
- Branch حداقل یک مورد
- Staff
- Role
- Membership
- active/inactive user

### Acceptance

Admin بتواند تیم Pilot را بدون تغییر code راه‌اندازی کند.

---

## 4.2 Role-Based Access

حداقل Roleها:

- Owner
- Manager
- Doctor
- Reception
- Coordinator
- Assistant

### Required

- permission checks در backend
- branch scope
- task visibility
- management visibility
- admin-only configuration

### Acceptance

کاربر نباید با URL، callback یا API بتواند data خارج از scope خود را بخواند یا تغییر دهد.

---

## 4.3 Patient Operational Reference

حداقل:

- internal ID
- display name
- optional contact reference
- doctor
- branch
- tags

### Acceptance

کاربر بتواند patient را پیدا و به task/case لینک کند.

### Boundary

پرونده بالینی جامع جزو MVP نیست.

---

## 4.4 Task / Action

حداقل:

- title
- owner
- due date/time
- priority
- status
- patient/case context
- created by
- created at
- completed at

### Acceptance

Create/Edit/Assign/Reassign/Complete/Reopen باید پایدار و permission-aware باشند.

---

## 4.5 Outcome

Taskهای workflow-based باید business outcome داشته باشند.

مثال Follow-up:

- Reached
- No Answer
- Scheduled
- Needs Time
- Declined
- Escalated

### Acceptance

Completion بدون Outcome در workflowهایی که outcome required است مجاز نباشد.

---

## 4.6 Next Action

هر case فعال باید بتواند Next Action مشخص داشته باشد.

حداقل:

- type
- owner
- due
- status

### Acceptance

Dashboard بتواند active caseهای بدون Next Action را flag کند.

---

## 4.7 Follow-up Queue

Views:

- Due Today
- Overdue
- Upcoming
- No Answer
- Rescheduled
- By Owner
- By Doctor

### Acceptance

Coordinator بتواند بدون Excel لیست follow-up روز خود را مدیریت کند.

---

## 4.8 Reminder

حداقل:

- before due
- at due
- overdue

### Acceptance

Reminder duplicate نشود و task completed را دوباره notify نکند.

---

## 4.9 Workflow Templates

MVP Pack:

### Template 1
Treatment Plan Follow-up

### Template 2
General Callback

### Template 3
Lab Case

### Template 4
Post-Treatment Follow-up

### Template 5
Daily Operations Checklist

### Acceptance

هر Template بدون development جدید برای یک کلینیک Pilot قابل configure باشد.

---

## 4.10 Comments

حداقل:

- create
- view
- timestamp
- author

### Acceptance

Comment فقط برای کاربران دارای permission قابل مشاهده باشد.

---

## 4.11 Search & Filters

حداقل جستجو:

- patient
- task
- owner
- status

حداقل filter:

- due
- overdue
- workflow
- doctor
- branch
- category

---

## 4.12 Telegram Execution

Frontline از Telegram باید بتواند:

- task ببیند
- task بسازد
- status عوض کند
- complete کند
- outcome انتخاب کند
- reminder بگیرد
- comment بگذارد
- personal queue ببیند

### Acceptance

کارهای P0 برای frontline نباید نیازمند Web باشند.

---

## 4.13 Web Management

Manager از Web باید بتواند:

- team setup
- queue view
- overdue
- filters
- workflow status
- reporting
- configuration
- audit view

### Acceptance

Manager بتواند Daily Review را بدون خروج از Web انجام دهد.

---

## 4.14 Dashboard

P0 Metrics:

- Open Tasks
- Due Today
- Overdue
- Unassigned
- Blocked
- Follow-ups Due
- Follow-ups Overdue
- Cases Without Next Action
- Workload by User

---

## 4.15 Audit Log

حداقل Eventها:

- create
- update
- assign
- reassign
- due change
- status change
- outcome change
- comment
- complete
- reopen
- permission change

### Acceptance

برای یک task مهم بتوان sequence تغییرات را بازسازی کرد.

---

## 4.16 Import / Export

### Import
CSV برای:
- patient references
- initial tasks در صورت نیاز

### Export
CSV برای:
- tasks
- follow-ups
- pilot metrics

### Acceptance

Pilot نباید برای ورود داده اولیه وابسته به migration سفارشی باشد.

---

# 5. Should Have — P1

اگر زمان و ظرفیت اجازه دهد:

- Voice-to-Task
- Natural-language task draft
- recurring tasks advanced
- saved filters
- manager digest
- basic calendar sync
- escalation rule
- dependencies
- attachment
- configurable outcome
- no-show recovery workflow
- recall workflow

این‌ها نباید launch MVP را block کنند مگر Pilot مشخصاً به آن‌ها وابسته باشد.

---

# 6. Could Have — P2

- advanced workflow designer
- multi-branch centralized dashboard
- patient-facing messaging
- WhatsApp/SMS automation
- PMS API connector
- payment integration
- advanced AI brief
- smart prioritization
- analytics benchmark

---

# 7. Not Now

MVP عمداً شامل این موارد نیست:

- EMR/EHR
- diagnosis
- clinical decision support
- prescription
- medical imaging archive
- insurance claim
- full accounting
- full payroll
- full inventory ERP
- full CRM
- public booking marketplace
- patient mobile app
- enterprise SSO
- advanced data warehouse
- autonomous clinical AI

---

# 8. MVP Workflow 1 — Treatment Plan Follow-up

## Start Condition

Patient consultation complete.

## Required

- patient
- owner
- due
- outcome
- next action

## Done

یکی از:
- Converted/Handoff
- Closed/Lost
- Follow-up Rescheduled

## Acceptance

هیچ patient در این workflow بدون Outcome یا Next Action نامشخص رها نشود.

---

# 9. MVP Workflow 2 — General Callback

## Start

هر درخواست callback.

## Required

- patient
- reason
- owner
- due

## Outcome

- resolved
- no answer
- needs doctor
- follow-up again
- closed

## Acceptance

Reception بتواند callback را در چند interaction ثبت کند.

---

# 10. MVP Workflow 3 — Lab Case

## Stages

- To Send
- Sent
- In Progress
- Expected
- Received
- Review
- Ready
- Completed
- Rework

## Acceptance

Overdue lab case باید قابل تشخیص باشد.

---

# 11. MVP Workflow 4 — Post-Treatment Follow-up

## Trigger

selected procedure completed.

## Required

- patient
- due
- responsible staff
- outcome

## Safety

Concern → human escalation.

هیچ clinical advice خودکار در MVP.

---

# 12. MVP Workflow 5 — Daily Checklist

## Trigger

recurring schedule.

## Roles

Reception / Assistant / Manager.

## Acceptance

Template هر روز taskهای لازم را تولید کند یا به‌سادگی instantiate شود.

---

# 13. UX Requirements

## Frontline

- mobile-first
- Telegram-first
- minimal fields
- one-tap common actions
- clear due time
- no dashboard overload

## Manager

- Web-first
- exception-centric
- saved views
- bulk visibility
- low-click review

## Doctor

- quick delegation
- approval
- exception only
- minimal administration

---

# 14. Performance Requirements

MVP باید target داخلی داشته باشد:

- task list response قابل استفاده در شرایط روزمره
- pagination اجباری برای لیست‌های بزرگ
- query filtering در database
- no full-table read برای visibility
- reminder jobs idempotent
- safe retry برای integrations
- concurrent update behavior مشخص

این‌ها Product Acceptance هستند، نه صرفاً technical nice-to-have.

---

# 15. Reliability Requirements

حداقل:

- no silent exception در critical paths
- structured logs
- error IDs
- retry policy
- duplicate-safe scheduled jobs
- startup health check
- database backup plan
- restore procedure tested

---

# 16. Security Requirements

قبل از Pilot با داده واقعی:

- tenant isolation
- cross-user authorization tests
- role permission tests
- secure secrets
- generic client errors
- audit
- export permission
- data minimization
- test environment بدون داده واقعی حساس

---

# 17. Privacy Requirements

در MVP:

- فقط minimum necessary operational data
- sensitive clinical narrative ذخیره نشود مگر ضروری
- attachment policy روشن
- retention policy تعریف شود
- role visibility مستند شود
- customer agreement درباره data boundaries روشن باشد

---

# 18. Instrumentation Requirements

برای هر Pilot باید eventهای زیر اندازه‌گیری شوند:

- task created
- task assigned
- task completed
- task overdue
- follow-up completed
- follow-up rescheduled
- no answer
- next action created
- case missing next action
- dashboard viewed
- Telegram action
- Web action

---

# 19. Pilot Baseline

قبل از شروع Pilot:

حداقل برای 1 تا 2 هفته یا با sample قابل اعتماد ثبت شود:

- تعداد follow-up
- missed follow-up estimate
- overdue
- current tools
- manager status time
- number of callbacks
- current workflow steps

بدون Baseline، ROI ادعایی ضعیف خواهد بود.

---

# 20. Pilot Scope

## Duration

Working range:

**4 تا 8 هفته**

این عدد فرضیه عملیاتی است و بسته به حجم workflow قابل تغییر است.

## Users

ترجیحاً:

**5 تا 15 کاربر واقعی**

## Workflows

فقط:

**2 workflow اصلی در هر Pilot**

نه کل Feature Catalog.

---

# 21. Pilot Success Targets

این اعداد **target اولیه برای validation** هستند، نه benchmark صنعت.

## Adoption

- حداقل 70% کاربران هدف در هفته فعال باشند
- حداقل 70% کارهای workflow منتخب داخل TaskMG ثبت شوند

## Data Quality

- حداقل 90% taskهای workflow owner داشته باشند
- حداقل 85% taskهای time-sensitive due داشته باشند

## Workflow

- حداقل 80% follow-upهای ثبت‌شده outcome داشته باشند
- case فعال بدون next action روند نزولی داشته باشد

## Management

- manager حداقل چند بار در هفته dashboard را برای کار واقعی استفاده کند
- daily/weekly report دستی کاهش یابد

## Commercial

- Economic Buyer در پایان Pilot تصمیم Paid/No-Paid مشخص بدهد

---

# 22. Pilot Failure Signals

- کاربران task را فقط برای demo ثبت می‌کنند
- manager مجبور است دائماً reminder دستی بدهد
- duplicate data entry شدید است
- پزشک باید admin work زیاد انجام دهد
- workflow به chat برمی‌گردد
- dashboard استفاده نمی‌شود
- customer فقط feature request می‌دهد ولی value نمی‌بیند
- Pilot بدون Buyer و deadline ادامه پیدا می‌کند

---

# 23. MVP Acceptance Criteria — Functional

MVP آماده Pilot است اگر:

1. Clinic setup بدون code change انجام شود.
2. Roleها permission واقعی داشته باشند.
3. Patient reference قابل جستجو باشد.
4. Task با owner/due/context ساخته شود.
5. Follow-up queue کار کند.
6. Outcome ثبت شود.
7. Next Action قابل تعریف باشد.
8. Reminder کار کند.
9. 5 template موجود باشد.
10. Dashboard exceptionها را نشان دهد.
11. Audit log وجود داشته باشد.
12. CSV import/export کار کند.
13. Telegram و Web یک داده واحد ببینند.
14. cross-user data leak در تست‌ها وجود نداشته باشد.

---

# 24. MVP Acceptance Criteria — Non-Functional

- critical endpoints pagination
- authorization backend-side
- structured logging
- generic external errors
- database indexes لازم
- reminder idempotency
- backup verified
- health checks
- no known P0 security bug
- core flow automated tests

---

# 25. Test Coverage Required Before Pilot

حداقل تست‌های جدی برای:

- team create/join/leave
- owner/editor/viewer or clinic role permissions
- user A cannot access user B data
- patient/case scope
- callback flows
- reminders
- scheduler concurrency
- startup jobs
- multi-bot isolation
- integration retry/idempotency
- audit creation

---

# 26. Data Migration Strategy

برای Pilot:

### Preferred
CSV import.

### Avoid
custom database migration per customer.

### Rule

اگر onboarding یک Pilot به script اختصاصی نیاز دارد، نیاز محصولی باید تحلیل شود؛ نباید فوراً customization دائمی ساخته شود.

---

# 27. Onboarding MVP

## Step 1
Clinic + Branch.

## Step 2
Users + Roles.

## Step 3
Import Patient References.

## Step 4
Choose 2 Workflows.

## Step 5
Configure owners/due/escalation.

## Step 6
Train by Role.

## Step 7
Go Live.

## Step 8
Daily Review first week.

---

# 28. Time-to-First-Value

هدف:

Customer باید در روز اول بتواند اولین workflow واقعی را اجرا کند.

Metric:

**Time from account ready → first real completed workflow**

---

# 29. Go / No-Go Gate برای Pilot

## Go

اگر:
- champion مشخص
- buyer مشخص
- 2 workflow مشخص
- baseline
- user list
- security scope accepted
- success criteria accepted

## No-Go

اگر:
- فقط demo curiosity
- buyer نامشخص
- custom build زیاد
- full EMR expectation
- integration شرط روز اول بدون امکان
- data risk خارج از capability

---

# 30. Definition of MVP Done

MVP زمانی Done است که:

- پنج workflow P0 technically قابل اجرا باشند؛
- حداقل دو workflow در یک Pilot واقعی end-to-end استفاده شده باشند؛
- adoption و outcome instrumentation وجود داشته باشد؛
- manager value ببیند؛
- major security blockers بسته شده باشند؛
- حداقل یک customer willingness-to-pay معتبر نشان دهد.

**MVP Done = workflow validated، نه feature list completed.**
