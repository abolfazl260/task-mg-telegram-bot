# نقشه راه محصول — Healthcare Clinics Roadmap

> وضعیت سند: Product Roadmap v1  
> اصل برنامه‌ریزی: Roadmap بر اساس **ریسک و شواهد** است، نه صرفاً تاریخ و تعداد Feature.  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه

---

# 1. فلسفه Roadmap

ترتیب توسعه باید این سؤال‌ها را به ترتیب پاسخ دهد:

1. آیا Pain واقعی و تکرارشونده است؟
2. آیا تیم کلینیک واقعاً از Action Loop استفاده می‌کند؟
3. آیا Follow-up/Case model ارزش بیشتری از Task Manager عمومی ایجاد می‌کند؟
4. آیا Manager حاضر است برای Visibility پول بدهد؟
5. آیا Workflow بین کلینیک‌ها repeatable است؟
6. کدام Integration واقعاً adoption یا ROI را بهتر می‌کند؟
7. آیا محصول می‌تواند چند شعبه و Vertical جدید را بدون fork پشتیبانی کند؟

بنابراین Roadmap به Phaseهای evidence-driven تقسیم می‌شود.

---

# 2. Baseline فعلی

هسته فعلی TaskMG قابلیت‌های قابل reuse مهمی دارد:

- Task
- Team
- Assignment
- Priority
- Deadline
- Reminder
- Comments
- Attachments
- Tags/Categories
- Search
- Reports
- Voice
- AI
- Templates
- Export
- Integration infrastructure
- Telegram bot
- Web dashboard

Vertical Healthcare نیازمند اضافه‌کردن یا تقویت این لایه‌هاست:

- Patient Operational Reference
- Case
- Follow-up Queue
- Outcome
- Next Action
- Clinic RBAC
- Vertical Templates
- Workflow Escalation
- Clinic Metrics
- Integration Mapping
- Data Boundaries

---

# 3. Phase 0 — Validation

## هدف

اثبات Pain، ICP و Workflow قبل از توسعه گسترده.

## Activities

- 15 تا 20 interview
- حداقل 5 workflow observation
- current-tool mapping
- pain ranking
- workflow frequency
- willingness-to-pay interview
- security/privacy expectation discovery

## Deliverables

- validated ICP
- top 5 workflows
- workflow maps
- baseline metrics
- Pilot candidates
- buyer/champion map

## Exit Gate

Phase 0 فقط زمانی Done است که:

- حداقل 3 کلینیک Pilot-ready باشند؛
- حداقل 2 workflow مشترک در چند کلینیک دیده شود؛
- Pain فقط «یادآوری» نباشد؛
- Buyer value در visibility/accountability ببیند؛
- یک مسیر commercial بعد از Pilot تعریف شود.

## Kill Signal

اگر بیشتر کلینیک‌ها Pain را با PMS فعلی کاملاً حل می‌کنند یا willingness to change پایین است، scope Vertical باید بازنگری شود.

---

# 4. Phase 1 — Clinic MVP

## هدف

ساخت حداقل System of Action قابل استفاده در Pilot واقعی.

## Product Scope

### P0 Domain
- Clinic
- Branch
- Staff
- Role
- Patient Reference
- Case پایه
- Outcome
- Next Action

### P0 Execution
- task
- owner
- due
- priority
- status
- comment
- reminder

### P0 Views
- personal queue
- follow-up queue
- overdue
- manager dashboard

### P0 Templates
- Treatment Plan Follow-up
- General Callback
- Lab Case
- Post-Treatment Follow-up
- Daily Checklist

### P0 Control
- RBAC
- audit
- import/export

## Technical Enablers

- database-side visibility filtering
- pagination
- tenant/branch scoping
- permission tests
- scheduler idempotency
- structured logging
- safe errors
- backup/restore baseline

## Exit Gate

- 2 workflows در Pilot واقعی
- >= 70% target users weekly active به‌عنوان هدف validation
- majority of workflow tasks owner/due دارند
- manager dashboard usage واقعی
- no critical authorization issue
- pilot decision from buyer

## Commercial Gate

حداقل یک:
- paid pilot
- paid conversion
- strong signed commercial commitment

---

# 5. Phase 2 — Workflow Automation

## هدف

تبدیل Manual Task System به Workflow Engine سبک.

## Features

- configurable outcomes
- automatic next action
- recurring templates
- escalation rules
- dependency
- waiting state
- SLA rules
- conditional follow-up
- workflow version
- template configuration

## Automation Examples

### No Answer
Outcome = No Answer  
→ Next Follow-up in N days

### Lab Overdue
Expected Date passed  
→ alert owner  
→ escalate manager

### Post-Treatment
Treatment event received  
→ create follow-up

### Missing Next Action
Case active + no next action  
→ flag

## Exit Gate

- حداقل 3 workflow بدون manual admin intervention
- automation duplicate-safe
- users automation را override/correct کنند
- measurable reduction in manual coordination

---

# 6. Phase 3 — Reporting & Management

## هدف

ساخت Management Value مستقل از frontline task list.

## Features

### Manager Dashboard
- backlog
- overdue
- blocked
- unassigned
- follow-up health
- case without next action
- workflow cycle time

### Owner Dashboard
- trend
- workflow volume
- completion trend
- adoption
- exception summary

### Reports
- weekly operations
- workflow outcome
- staff workload
- branch readiness

## AI

- daily manager brief
- overdue summary
- safe natural-language reporting

## Exit Gate

- manager dashboard weekly retention بالا
- manual status-report effort کاهش قابل مشاهده
- buyer بتواند value را با operational metric توضیح دهد

---

# 7. Phase 4 — Integrations

## هدف

کاهش duplicate data entry و اتصال TaskMG به System of Record.

## Integration Priority

### 4A — Calendar
- Google Calendar
- Microsoft Outlook Calendar

Use:
- appointment event
- cancellation/no-show trigger where possible
- scheduled task context

### 4B — Clinic Software
- CSV/import first
- API connector where demand repeats

### 4C — Communication
- email
- SMS provider
- WhatsApp provider

### 4D — Webhooks/API
- external trigger
- external outcome

## Architecture Requirements

- idempotency
- external object link
- sync cursor
- retry
- dead-letter/error state
- OAuth token lifecycle
- webhook verification
- audit

## Exit Gate

Integration باید حداقل یکی را اثبات کند:

- duplicate entry meaningful reduction
- faster follow-up
- automatic trigger creation
- sales blocker removal

Integration بدون outcome وارد roadmap پایدار نشود.

---

# 8. Phase 5 — Multi-Branch

## هدف

تبدیل محصول از single-clinic tool به operational platform.

## Data Model

- Organization
- Branch
- Branch Membership
- Central Role
- Branch Role

## Features

- branch-scoped access
- central template
- local override
- cross-branch dashboard
- branch comparison
- branch-level workflow metrics
- cross-branch handoff
- organization-level audit

## Technical Requirements

- tenant isolation hardened
- query scope mandatory
- branch indexes
- permission matrix
- scalable reporting
- centralized configuration

## Exit Gate

- یک multi-branch customer واقعی
- no cross-branch leakage
- central manager uses consolidated dashboard
- same template deployed to multiple branches

---

# 9. Phase 6 — Vertical Expansion

## هدف

اثبات اینکه Core + Domain Layer قابل reuse است.

## Candidate Verticals

### Beauty / Dermatology
نیاز بیشتر:
- lead pipeline
- package/session follow-up

### Physiotherapy
نیاز بیشتر:
- treatment course
- session adherence

### Specialist Physician Practices
نیاز بیشتر:
- test/document follow-up
- referral

## Rule

Vertical جدید نباید fork کامل codebase باشد.

ساختار:

Core  
+ Healthcare Common Layer  
+ Vertical Configuration

## Exit Gate

حداقل 70-80% capability reuse به‌عنوان هدف معماری، نه KPI قراردادی.

---

# 10. Phase 7 — Advanced Intelligence

## هدف

AI به لایه operational intelligence تبدیل شود، بعد از تثبیت workflow.

## Features

- action extraction
- case summary
- workflow risk detection
- suggested next action
- workload recommendation
- anomaly detection
- natural-language analytics

## Guardrail

AI تصمیم بالینی خودکار نمی‌گیرد.

## Exit Gate

- evaluated accuracy
- low unsafe-action rate
- human override
- audit trail
- measurable time saved

---

# 11. Roadmap by Capability

| Capability | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6+ |
|---|---|---|---|---|---|---|
| Task Core | Mature | Improve | — | — | Scale | — |
| Patient Reference | Basic | Improve | Report | Sync | Multi-branch | Verticalize |
| Case | Basic | Advanced | Analytics | Sync | Cross-branch | Verticalize |
| Next Action | Basic | Automated | Analytics | External trigger | Scale | AI |
| Templates | 5 fixed | Configurable | Analytics | Triggered | Central | Library |
| Follow-up | Queue | Rules | Metrics | Messaging | Branch | Vertical variants |
| Dashboard | Basic | Exceptions | Advanced | Integrated | Consolidated | Benchmark |
| AI | Optional | Assist | Brief | Context | Multi-branch | Advanced |
| Integrations | Import/export | Foundation | — | Major | Enterprise | Ecosystem |
| RBAC | Clinic | Fine-grained | Audit | Scopes | Hierarchy | Enterprise |

---

# 12. Roadmap by Workflow

## Treatment Plan Follow-up
Phase 1: manual  
Phase 2: automatic retry/outcome  
Phase 3: conversion analytics  
Phase 4: PMS trigger

## Lab Case
Phase 1: stages  
Phase 2: due/escalation/dependency  
Phase 3: turnaround metrics  
Phase 4: lab integration if justified

## Post-Treatment
Phase 1: manual/scheduled  
Phase 2: automatic generation  
Phase 3: escalation metrics  
Phase 4: event trigger

## Daily Operations
Phase 1: recurring template  
Phase 2: rule-based  
Phase 3: compliance trend  
Phase 5: branch comparison

---

# 13. Technical Roadmap

## Foundation

- service boundaries
- async-safe database access
- permission service
- pagination
- indexes
- audit events

## Workflow Engine

- template
- instance
- state transition
- outcome
- trigger
- rule

## Integration Platform

- provider abstraction
- connection
- external link
- webhook endpoint
- retry queue
- sync cursor

## Analytics

- event capture
- operational aggregates
- report service

## AI

- structured tool calling
- permission-aware context
- action confirmation
- evaluation harness

---

# 14. Security Roadmap

## Before First Pilot

- authorization regression tests
- cross-user isolation
- clinic role tests
- secure secrets
- safe errors
- audit
- backups

## Before Multi-Branch

- tenant hardening
- branch scope
- export permission
- retention
- security review

## Before Enterprise

- SSO
- advanced audit
- security documentation
- incident procedures
- contractual/compliance assessment by jurisdiction

---

# 15. Data Roadmap

## Phase 1

Operational data only.

## Phase 2

Case/outcome/history.

## Phase 3

Aggregated metrics.

## Phase 4

External references.

## Phase 5

Branch hierarchy.

## Principle

هر مرحله باید از جمع‌آوری داده‌ای که برای JTBD ضروری نیست اجتناب کند.

---

# 16. Release Gates

هر release باید از چهار Gate عبور کند:

## Product Gate
JTBD و Persona مشخص.

## Engineering Gate
tests + observability + migration.

## Security Gate
permissions + data boundary.

## Measurement Gate
metric و event instrumentation.

---

# 17. Feature Intake Process

Feature Request مستقیماً وارد Roadmap نشود.

فرآیند:

Request  
→ JTBD  
→ Frequency  
→ Segment  
→ Workaround  
→ Revenue/Retention Impact  
→ Architecture Fit  
→ Priority

---

# 18. Customer Customization Policy

## Allow

- configuration
- custom fields محدود
- template settings
- branding
- role settings

## Review Carefully

- custom integration
- unique workflow

## Avoid

- customer-specific fork
- hardcoded business rule
- separate database schema per small customer

---

# 19. Roadmap Metrics

## Phase 1

- activation
- workflow completion
- WAU
- overdue
- pilot conversion

## Phase 2

- automation adoption
- manual steps reduced
- exception rate

## Phase 3

- dashboard retention
- manager reporting time

## Phase 4

- sync success
- integration-triggered actions
- duplicate entry reduced

## Phase 5

- branch rollout time
- organization retention
- expansion revenue

---

# 20. Prioritization Formula

پیشنهاد:

**Priority Score = Pain × Frequency × Strategic Fit × Evidence × Revenue/Retention Impact ÷ Complexity/Risk**

این فرمول تصمیم را جایگزین judgment نمی‌کند؛ فقط trade-off را شفاف می‌کند.

---

# 21. Dependencies That Can Block Roadmap

- weak permission model
- unscoped database reads
- unstable scheduler
- lack of audit
- no patient/case model
- no event/outcome model
- excessive custom code
- missing integration abstraction

این موارد باید قبل از Scale حل شوند.

---

# 22. Critical Sequencing Decisions

## Workflow قبل از AI
AI نباید process نامشخص را automate کند.

## Data Model قبل از Multi-Branch
scope بعداً با patch امن نمی‌شود.

## Pilot قبل از Broad Integration
connector بدون اثبات workflow هزینه sink است.

## Outcome قبل از Advanced Analytics
اگر فقط status داریم، business insight ضعیف خواهد بود.

---

# 23. What We Do Not Schedule Yet

تا وقتی evidence نداریم، تاریخ مشخص برای این موارد داده نمی‌شود:

- full CRM
- patient portal
- billing
- insurance
- deep FHIR integration
- enterprise SSO
- benchmark network

این‌ها opportunity هستند، نه commitment.

---

# 24. معیار ورود به هر فاز

| Phase | Entry Gate |
|---|---|
| Validation | Market hypothesis |
| Clinic MVP | Repeated pain + pilot candidates |
| Automation | Manual workflow adopted |
| Reporting | Sufficient workflow data |
| Integrations | Repeated duplicate-entry pain |
| Multi-Branch | Real multi-location demand |
| Expansion | Dental PMF evidence |
| Advanced AI | Stable workflows + eval framework |

---

# 25. معیار خروج از هر فاز

| Phase | Exit Evidence |
|---|---|
| Validation | 2+ repeatable workflows |
| Clinic MVP | Real usage + commercial signal |
| Automation | Rules save manual work |
| Reporting | Managers rely on dashboard |
| Integrations | Measurable integration value |
| Multi-Branch | Central operations works safely |
| Expansion | High core reuse |
| AI | Measurable safe productivity gain |

---

# 26. Roadmap Review Cadence

Roadmap باید حداقل بعد از هر یک از این اتفاق‌ها بازبینی شود:

- پایان Pilot
- lost deal pattern
- security finding
- major integration blocker
- churn
- expansion request
- pricing change

---

# 27. تصمیم Roadmap فعلی

ترتیب پیشنهادی:

**Validate → Clinic MVP → Workflow Automation → Management Analytics → Integrations → Multi-Branch → Vertical Expansion → Advanced Intelligence**

اگر تیم این ترتیب را بشکند و قبل از PMF به سمت PMS جامع، integrationهای متعدد یا AI پیچیده برود، ریسک scope creep و کاهش سرعت یادگیری بالا می‌رود.
