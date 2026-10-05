# پیاده‌سازی و Customization — Healthcare Clinics

> وضعیت سند: Implementation & Customization Playbook v1  
> هدف: راه‌اندازی سریع، قابل تکرار و کم‌ریسک کلینیک‌ها بدون تبدیل هر مشتری به پروژه نرم‌افزاری اختصاصی.  
> اصل: **Configuration first, customization second, custom code last.**

---

# 1. Implementation Objective

هدف Implementation این است که کلینیک:

- سریع به First Value برسد؛
- فقط workflowهای لازم را شروع کند؛
- staff سردرگم نشوند؛
- داده اولیه درست وارد شود؛
- roleها و access درست باشند؛
- manager بتواند workflow را کنترل کند؛
- Product بدون code fork برای customer کار کند.

---

# 2. Implementation Tiers

## Tier 1 — Standard Setup

مناسب:
- single branch
- small team
- standard dental workflows

شامل:
- organization setup
- users/roles
- CSV import
- 2 standard workflows
- basic dashboard
- training
- go-live support

---

## Tier 2 — Configured Clinic

مناسب:
- medium clinic
- multiple doctors
- custom terminology
- several workflows

شامل Tier 1 +
- workflow configuration
- custom fields محدود
- report views
- escalation rules
- calendar/basic integration

---

## Tier 3 — Multi-Branch / Advanced

مناسب:
- multiple branches
- central manager
- integration needs

شامل:
- branch hierarchy
- central templates
- branch-specific config
- advanced roles
- consolidated reports
- rollout plan

---

## Tier 4 — Strategic / Enterprise

برای:
- complex integration
- security review
- custom SLA
- enterprise identity
- advanced reporting

نیازمند Statement of Work جدا.

---

# 3. Standard Configuration

Standard Configuration باید بدون code انجام شود.

## Includes

- clinic name
- timezone
- branch
- staff
- roles
- categories
- tags
- notification preferences
- workflow templates
- due rules
- outcome options
- dashboard filters

---

# 4. Clinic Configuration

هر clinic حداقل این تصمیم‌ها را دارد:

## Organization

- name
- timezone
- language
- admin

## Branch

- branch name
- manager
- operating hours

## Team

- users
- role
- branch scope

## Operations

- daily workflows
- escalation
- notification

---

# 5. Dental Configuration

## Default Roles

- Owner
- Clinic Manager
- Dentist
- Reception
- Treatment Coordinator
- Assistant

## Default Workflow Pack

- Treatment Plan Follow-up
- Callback
- Lab Case
- Post-Treatment
- Daily Checklist

## Optional

- No-show Recovery
- Recall
- Complaint
- Implant Case
- Orthodontic Flow

---

# 6. Medical Practice Configuration

برای مطب پزشک:

## Roles

- Physician
- Reception
- Nurse/Assistant
- Manager

## Workflows

- Callback
- Test/Document Follow-up
- Referral
- Post-visit Action
- No-show Recovery

## Boundary

clinical interpretation خارج از workflow automation.

---

# 7. Beauty Clinic Configuration

## Roles

- Clinic Owner
- Consultant
- Reception
- Practitioner
- Sales/Coordinator

## Workflows

- Inquiry Follow-up
- Consultation
- Package Follow-up
- Session Series
- Rebooking
- Complaint

## Difference

CRM-like lead stage importance بالاتر است.

---

# 8. Physiotherapy Configuration

## Roles

- Therapist
- Reception
- Manager

## Workflows

- Assessment Follow-up
- Treatment Course
- Missed Session
- Rebooking
- Progress Checkpoint
- Discharge Follow-up

---

# 9. Implementation Phases

## Phase 1 — Discovery

- business goals
- current tools
- workflow map
- users
- data sources
- security requirements
- success metrics

## Phase 2 — Solution Design

- choose workflows
- role map
- data map
- integration scope
- reports
- rollout scope

## Phase 3 — Configuration

- tenant
- branch
- users
- permissions
- templates
- notifications
- dashboards

## Phase 4 — Data Setup

- import
- dedupe
- validation
- sample check

## Phase 5 — Training

role-based.

## Phase 6 — Go-Live

limited workflows.

## Phase 7 — Hypercare

monitor adoption/issues.

## Phase 8 — Review

measure success and expand.

---

# 10. Discovery Checklist

قبل از configuration:

- چه مشکل اصلی را حل می‌کنیم؟
- کدام workflow؟
- current workaround؟
- owner هر workflow؟
- volume؟
- due/SLA؟
- outcome؟
- escalation؟
- patient context؟
- current software؟
- integration؟
- success criteria؟
- buyer/champion؟

---

# 11. Workflow Discovery Template

برای هر workflow:

## Trigger

چه اتفاقی شروعش می‌کند؟

## Actors

چه کسانی؟

## Owner

accountable person/role.

## Steps

current steps.

## Data

چه context لازم است؟

## Due

deadline.

## Outcome

success/failure.

## Exception

چه چیزی گیر می‌کند؟

## Metric

چه چیزی بهتر می‌شود؟

---

# 12. Workflow Customization Levels

## Level 0 — Standard Template

بدون تغییر.

## Level 1 — Configuration

- owner role
- timing
- reminders
- outcomes

## Level 2 — Custom Fields / Rules

محدود و reusable.

## Level 3 — Integration

external trigger/data.

## Level 4 — Product Extension

فقط اگر reusable برای segment.

## Level 5 — Customer-specific Code

exceptional and discouraged.

---

# 13. Customization Decision Rule

قبل از قبول customization:

1. چند customer نیاز دارند؟
2. آیا با config حل می‌شود؟
3. آیا core architecture را خراب می‌کند؟
4. maintenance cost چیست؟
5. revenue justification چیست؟
6. security impact؟
7. آیا roadmap conflict دارد؟

---

# 14. Customization Governance

هر request یکی از statusها:

- Configure
- Template
- Product Candidate
- Paid Customization
- Reject
- Later

Decision باید documented باشد.

---

# 15. Branding

## Standard

- clinic name
- logo
- basic labels

## Advanced

- custom domain
- email branding
- report branding

## Avoid Early

- deep UI fork
- customer-specific theme code
- separate application build

---

# 16. Terminology Customization

کلینیک ممکن است terminology متفاوت داشته باشد.

مثال:

- Patient / Client
- Case / Treatment Case
- Coordinator / Consultant

## Rule

Display labels configurable باشند، اما internal domain key ثابت بماند.

---

# 17. Field Customization

## Allowed Types

- text
- number
- date
- boolean
- enum
- reference

## Governance

Custom field باید:

- owner داشته باشد
- purpose داشته باشد
- report need مشخص باشد
- data classification داشته باشد

## Avoid

free-form fields زیاد.

---

# 18. Report Customization

## Level 1

saved filters/views.

## Level 2

configurable dashboard widgets.

## Level 3

custom report/query.

## Level 4

BI/export integration.

هدف:
بیشتر نیازها با Level 1/2 حل شوند.

---

# 19. Integration Customization

## Standard Connector

product-supported.

## Configured Connector

field mapping/customer credentials.

## Custom Connector

project scope.

Custom Connector باید:

- API review
- data map
- auth
- retry
- monitoring
- ownership
- maintenance

داشته باشد.

---

# 20. Data Migration

## Preferred

CSV.

## Steps

1. source inventory
2. field mapping
3. sample export
4. normalization
5. duplicate detection
6. dry run
7. customer validation
8. final import
9. reconciliation

---

# 21. Data Migration Scope

MVP migration باید محدود باشد.

## Usually Migrate

- active patient references
- open follow-ups
- open cases if needed

## Usually Avoid

- years of historical clinical data
- old closed tasks
- full chart history

---

# 22. Data Quality

قبل از import:

- missing ID
- duplicate
- invalid phone
- unknown doctor
- invalid date
- branch mapping

report شود.

Customer باید data mapping را approve کند.

---

# 23. User Provisioning

Process:

- user list
- role
- branch
- identity mapping
- invite
- verification
- first login
- training

Offboarding نیز از روز اول تعریف شود.

---

# 24. Role Mapping Workshop

جدول:

| Clinic Role | TaskMG Role | Scope |
|---|---|---|
| Owner | Owner | Organization |
| Manager | Manager | Branch/Org |
| Dentist | Doctor | Related |
| Reception | Reception | Branch |
| Coordinator | Coordinator | Branch |
| Assistant | Assistant | Branch |

Exceptionها مستند شوند.

---

# 25. Notification Setup

برای هر role:

- immediate events
- due reminders
- overdue
- digest
- quiet hours

notification default باید conservative باشد تا fatigue ایجاد نشود.

---

# 26. Training Strategy

Training باید role-based باشد.

## Reception

- create callback
- queue
- outcome
- reschedule

## Coordinator

- follow-up
- next action
- case

## Manager

- assign
- dashboard
- overdue
- escalation

## Doctor

- delegate
- approve
- exceptions

## Owner

- dashboard
- trends

---

# 27. Training Format

پیشنهاد:

- short live session
- scenario-based
- cheat sheet
- short video
- first-week office hours

نه یک training طولانی برای همه roleها.

---

# 28. Train-the-Trainer

برای clinic متوسط:

یک internal champion آموزش عمیق‌تر ببیند.

Responsibilities:

- basic questions
- adoption follow-up
- workflow feedback
- new staff onboarding

---

# 29. Change Management

Change resistance باید مدیریت شود.

## Explain Why

problem and value.

## Start Small

2 workflows.

## Involve Users

frontline feedback.

## Show Quick Win

first week.

## Avoid Surveillance Framing

metrics برای process improvement.

---

# 30. Communication Plan

Before Go-live:

- why
- what changes
- what does not change
- where to ask help
- go-live date

After Go-live:

- daily/weekly reminders
- feedback channel
- success story

---

# 31. Pilot Implementation

Pilot باید scope ثابت داشته باشد.

## Required

- champion
- buyer
- users
- workflows
- baseline
- metrics
- start
- end
- decision date

---

# 32. Pilot Configuration Freeze

بعد از go-live:

تغییرهای بزرگ workflow محدود شوند تا measurement قابل اعتماد بماند.

Critical fix exception است.

---

# 33. Hypercare

هفته‌های اول:

- usage review
- error review
- workflow friction
- support
- data quality

هدف:
fix adoption blockers سریع.

---

# 34. Go-Live Checklist

## Product

- tenant
- branch
- users
- roles
- workflows
- dashboard

## Data

- import
- sample validation
- duplicates checked

## Security

- role tests
- admin list
- export permission

## Operations

- support contact
- incident path
- champion

## Measurement

- baseline
- events
- success metrics

---

# 35. Rollback Plan

اگر go-live issue جدی دارد:

- stop new workflow
- preserve data
- revert integration trigger
- restore configuration
- communicate
- incident review

برای migration destructive از rollback-safe process استفاده شود.

---

# 36. Implementation Acceptance Criteria

Customer sign-off روی:

- user/role list
- workflow config
- data mapping
- dashboard
- notification
- support process

داشته باشد.

---

# 37. Time-to-Value

Primary Implementation KPI:

**Account Ready → First Real Workflow Completed**

Secondary:

- days to onboarding complete
- hours of implementation
- support tickets first 30 days

---

# 38. Implementation Cost Control

Track:

- discovery hours
- config hours
- migration hours
- training hours
- support

هدف:
هر cohort بعدی با template هزینه کمتر داشته باشد.

---

# 39. Standardization Target

Implementation باید به سمت:

**80% Standard + 20% Configuration**

حرکت کند.

این عدد یک working target است، نه قانون ثابت.

اگر عکس شد، Product احتمالاً custom-services heavy شده است.

---

# 40. Multi-Branch Rollout

بهتر است:

## Step 1

Pilot branch.

## Step 2

template stabilize.

## Step 3

branch 2.

## Step 4

central reporting.

## Step 5

remaining branches.

Big-bang rollout پرریسک‌تر است.

---

# 41. Central vs Local Configuration

## Central

- standard workflow
- role policy
- reporting definitions

## Local

- staff
- schedules
- limited notification
- branch-specific operational detail

---

# 42. Customer Success Handoff

Implementation → CS handoff شامل:

- objectives
- workflows
- users
- champion
- risks
- open issues
- baseline
- success metrics
- expansion opportunities

---

# 43. Support Handoff

Support باید بداند:

- config
- integrations
- known limitations
- priority users
- escalation contacts

---

# 44. Implementation Documentation

برای هر customer:

- solution design
- role matrix
- workflow config
- data mapping
- integration map
- go-live checklist
- training record
- acceptance
- open risks

---

# 45. Configuration Versioning

Workflow/config change باید:

- date
- author
- reason
- previous value
- new value

قابل audit باشد.

---

# 46. Production Change Policy

Major workflow change:

- review
- test
- schedule
- notify
- deploy
- monitor

نباید manager config ناخواسته operational flow را خراب کند.

---

# 47. Sandbox / Test Clinic

برای configuration پیچیده:

test tenant یا sandbox مفید است.

استفاده از synthetic data ترجیح دارد.

---

# 48. Implementation Roles

## Customer

### Economic Buyer
approve.

### Champion
drive adoption.

### Admin/Manager
configuration.

### Users
training/use.

## TaskMG

### Implementation Lead
scope/config.

### Product/Engineering
technical issues.

### Customer Success
adoption/value.

### Security/Privacy
complex data/security review.

---

# 49. RACI Example

| Activity | Customer Owner | Champion | TaskMG Implementation | Engineering |
|---|---|---|---|---|
| Goals | A | R | R | I |
| Workflow Map | I | R | A/R | I |
| User Roles | A | R | R | I |
| Data Import | C | R | A/R | C |
| Integration | I | C | A | R |
| Training | I | R | A/R | I |
| Go-live | A | R | R | C |

A = Accountable, R = Responsible, C = Consulted, I = Informed.

---

# 50. Scope Change Process

اگر customer وسط implementation request جدید داد:

1. document request
2. impact
3. classify
4. estimate
5. approve/reject
6. update scope

Scope creep silently پذیرفته نشود.

---

# 51. Custom Development Contracting

اگر code customization لازم شد:

- explicit scope
- acceptance
- ownership/IP terms
- maintenance
- support
- upgrade compatibility
- fee

روشن باشد.

---

# 52. Reusable Product Feedback

هر customization بعد از delivery بررسی شود:

- آیا 3+ customer potential دارد؟
- آیا باید core feature شود؟
- آیا template شود؟
- آیا retire شود؟

---

# 53. Implementation Metrics

- Time to First Value
- Implementation Hours
- Go-live Delay
- Import Error Rate
- Training Attendance
- First-week WAU
- First-month WAU
- Support Tickets
- Configuration Changes
- Pilot Success
- Expansion

---

# 54. Implementation Risks

- no champion
- bad data
- role confusion
- too many workflows
- integration delay
- notification overload
- user resistance
- scope creep
- security blocker

هر project باید risk log داشته باشد.

---

# 55. Exit Criteria — Implementation

Implementation complete است وقتی:

1. agreed workflows live هستند؛
2. users role access دارند؛
3. data validated شده؛
4. dashboard کار می‌کند؛
5. training انجام شده؛
6. support path روشن است؛
7. measurement فعال است؛
8. customer acceptance دارد.

---

# 56. Exit Criteria — Pilot to Production

- adoption threshold acceptable
- workflow value demonstrated
- major bugs closed
- security scope accepted
- commercial agreement
- production support plan
- next-phase scope

---

# 57. Customization Anti-patterns

نباید:

- customer-specific branch دائمی
- hardcoded clinic name/business rule
- unique schema per clinic
- report in code when filter solves it
- integration بدون monitoring
- field بدون purpose
- custom workflow بدون versioning
- implementation بدون success metric

---

# 58. Implementation Playbook Maturity

## Level 1 — Founder-led

manual.

## Level 2 — Documented

checklists/templates.

## Level 3 — Repeatable

implementation specialist can deliver.

## Level 4 — Productized

self-service + guided setup.

## Level 5 — Partner-led

certified implementation partners possible.

---

# 59. Long-term Goal

Implementation باید از «مشاوره سفارشی» به «configuration guided by best-practice templates» تبدیل شود.

این برای:

- margin
- scale
- quality
- faster onboarding

ضروری است.

---

# 60. تصمیم فعلی

Default engagement:

**Standard Clinic Setup + 2 Workflow Launch + Role-based Training + Measured Pilot**

Customization باید استثنا باشد، نه مدل اصلی کسب‌وکار.
