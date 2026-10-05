# Metrics و KPIها — Healthcare Clinics

> وضعیت سند: Metrics Framework v1  
> هدف: تعریف یک سیستم اندازه‌گیری مشترک برای Product، Sales، Operations و Customer Outcomes.  
> اصل: KPI باید به تصمیم منجر شود؛ metric بدون owner و action ارزش مدیریتی ندارد.

---

# 1. North Star Metric

## Primary North Star

**Completed On-Time Actions per Active Clinic**

چرا؟

- فقط activity نیست؛
- execution واقعی را می‌سنجد؛
- با promise محصول هم‌راستاست؛
- بین کلینیک‌ها قابل مقایسه است؛
- با adoption و workflow quality ارتباط دارد.

## Supporting North Star

**% Active Cases with a Valid Next Action**

این metric differentiation اصلی محصول را می‌سنجد.

---

# 2. Metric Hierarchy

## Level 1 — Business Health

- ARR / MRR
- NRR
- GRR
- Logo Retention
- CAC Payback

## Level 2 — Product Value

- Completed On-Time Actions
- Follow-up Completion
- Cases with Next Action
- Manager Dashboard Usage

## Level 3 — Product Behavior

- Active Users
- Tasks Created
- Workflows Started
- Outcomes Recorded
- Reminders Triggered

## Level 4 — Operational Quality

- Error Rate
- Latency
- Scheduler Success
- Integration Health
- Support Load

---

# 3. Metric Definition Standard

هر KPI باید این metadata را داشته باشد:

- Name
- Definition
- Formula
- Data Source
- Owner
- Frequency
- Segmentation
- Target
- Alert Threshold
- Action if Bad

---

# 4. Acquisition Metrics

## Qualified Leads

Leadهایی که ICP threshold را پاس می‌کنند.

## ICP Fit Rate

**Qualified Leads / Total Leads**

## Lead Source

- outbound
- referral
- partner
- event
- inbound
- paid
- organic

## Cost per Qualified Lead

**Channel Cost / Qualified Leads**

## Discovery Conversion

**Discovery Meetings / Qualified Leads**

---

# 5. Activation Metrics

Activation زمانی رخ می‌دهد که clinic فقط account نسازد، بلکه workflow واقعی اجرا کند.

## Suggested Activation Event

Clinic activated if:

1. staff invited
2. first workflow configured
3. first real task created
4. first real task completed
5. manager views operational dashboard

## Activation Rate

**Activated Clinics / New Clinics**

## Time to Activation

signup/setup → activation event.

## Time to First Value

setup ready → first meaningful completed workflow.

---

# 6. Onboarding Metrics

- setup duration
- number of training sessions
- import success
- users invited
- users activated
- workflow configuration hours
- onboarding support tickets
- first-week usage

## Onboarding Completion Rate

clinics completing required onboarding checklist.

---

# 7. Product Usage Metrics

## WAU

Weekly Active Users.

Active = meaningful operational action, نه صرف login.

Examples:
- create task
- complete task
- record outcome
- comment
- manager review

## Clinic WAU

تعداد clinicهایی که حداقل یک workflow action واقعی داشته‌اند.

## Role Activity

- Reception WAU
- Manager WAU
- Coordinator WAU
- Doctor WAU

## Telegram vs Web

- actions from Telegram
- actions from Web

این metric adoption channel را نشان می‌دهد، نه success به‌تنهایی.

---

# 8. Task Metrics

- Tasks Created
- Tasks Completed
- Tasks Completed On Time
- Overdue Tasks
- Reopened Tasks
- Cancelled Tasks
- Unassigned Tasks
- Tasks Without Due Date

## On-Time Completion Rate

**Tasks Completed On or Before Due / Time-sensitive Tasks Completed**

## Overdue Rate

**Open Overdue Tasks / Open Time-sensitive Tasks**

---

# 9. Follow-up Metrics

## Follow-up Completion Rate

**Follow-ups with Recorded Outcome / Follow-ups Due**

## Median Time to First Follow-up

event/trigger → first contact attempt.

## No Answer Rate

**No Answer Outcomes / Follow-up Attempts**

## Reschedule Rate

## Follow-ups Without Outcome

Critical data-quality metric.

## Overdue Follow-up Rate

---

# 10. Next Action Metrics

## Cases with Valid Next Action

**Active Cases with Next Action / Active Cases**

## No-next-action Count

هدف:
near-zero برای workflowهایی که Next Action required است.

## Next Action Overdue

active case whose current next action is overdue.

---

# 11. Workflow Completion Metrics

برای هر workflow:

- Started
- Completed
- Cancelled
- Stuck
- Median Cycle Time
- Stage Drop-off
- Overdue Rate
- Escalation Rate
- Outcome Distribution

## Workflow Completion Rate

**Completed Instances / Eligible Closed + Active Cohort**

تعریف denominator باید ثابت باشد.

---

# 12. Treatment Plan Follow-up KPIs

- plans entering workflow
- first follow-up completed
- time to first follow-up
- cases with next action
- outcome distribution
- scheduled/converted outcome
- declined
- no answer
- unresolved

اگر revenue conversion اندازه‌گیری می‌شود، باید data source و تعریف مالی روشن باشد.

---

# 13. Lab Workflow KPIs

- open lab cases
- overdue lab cases
- median turnaround
- rework
- appointment-at-risk
- stage delays

---

# 14. Post-Treatment KPIs

- eligible procedures
- follow-up created
- follow-up completed
- completion on time
- concerns escalated
- no answer

---

# 15. Daily Operations KPIs

- checklist generated
- checklist completed
- on-time completion
- repeated missed items
- exception count

---

# 16. Management Metrics

## Manager Dashboard WAU

آیا manager واقعاً محصول را برای کنترل استفاده می‌کند؟

## Review Frequency

- daily
- weekly

## Time Spent on Manual Status Gathering

قبل/بعد Pilot.

## Exceptions Resolved

- escalated
- blocked
- unassigned

---

# 17. Adoption Depth

فقط WAU کافی نیست.

## Workflow Penetration

**Target Workflow Actions Captured in TaskMG / Estimated Total Target Actions**

## Multi-Workflow Adoption

تعداد workflowهای فعال per clinic.

## Role Coverage

تعداد roleهایی که active هستند.

## Stickiness

WAU/MAU برای userهایی که daily workflow دارند.

---

# 18. Retention Metrics

## Logo Retention

کلینیک‌های باقی‌مانده.

## Gross Revenue Retention

## Net Revenue Retention

## Product Retention

clinic still executes workflows.

## Cohort Retention

بهتر است بر اساس:
- activation month
- segment
- clinic size
- workflow type

تحلیل شود.

---

# 19. Churn Metrics

## Churn Reason

اجباری و structured:

- no value
- low adoption
- price
- champion left
- feature gap
- integration gap
- security/compliance
- business closed
- competitor
- support issue
- other

## Pre-Churn Signals

- WAU decline
- dashboard inactive
- workflow volume decline
- support frustration
- no champion
- overdue configuration issue

---

# 20. Revenue Metrics

- MRR
- ARR
- New MRR
- Expansion MRR
- Contraction MRR
- Churned MRR
- ARPA
- Setup Revenue
- Services Revenue

## Revenue by Segment

- Small Dental
- Medium Dental
- Multi-Branch
- Other Vertical

---

# 21. Sales Metrics

## Pipeline

- Lead
- Qualified
- Discovery
- Demo
- Pilot Proposed
- Pilot Active
- Pilot Success
- Paid
- Lost

## Conversion per Stage

## Sales Cycle Length

Qualified → Paid.

## Pilot-to-Paid Conversion

یکی از مهم‌ترین KPIهای early GTM.

## Win Rate

## Loss Reasons

structured.

---

# 22. Pricing Metrics

- average discount
- plan mix
- annual vs monthly
- setup fee collected
- add-on attach rate
- willingness-to-pay feedback
- price-related loss rate

---

# 23. CAC Metrics

- blended CAC
- channel CAC
- sales-assisted CAC
- CAC payback

## Early Stage

Founder time و Pilot delivery باید در محاسبه پنهان نشوند.

---

# 24. Unit Economics Metrics

- Gross Margin
- Contribution Margin
- COGS per Clinic
- Support Cost per Clinic
- AI Cost per Clinic
- Messaging Cost per Clinic
- Implementation Cost
- 12-month Gross Profit

---

# 25. Support Metrics

- Tickets per Clinic
- Tickets per Active User
- First Response Time
- Resolution Time
- Reopen Rate
- Severity Mix
- Repeat Issue Rate
- Support CSAT

## Support Classification

- Bug
- UX confusion
- Training
- Configuration
- Integration
- Data issue
- Feature request

---

# 26. Reliability Metrics

- API success rate
- p50/p95 latency
- bot callback failure
- scheduler job success
- reminder delivery success
- integration sync success
- webhook failure
- error volume
- uptime

---

# 27. Security Metrics

- unauthorized access attempts
- permission test pass rate
- high-risk findings open
- secret rotation status
- backup success
- restore test age
- audit coverage
- privileged accounts
- stale accounts

## Important

Security KPI نباید فقط «تعداد incident = صفر» باشد؛ absence of detection ≠ absence of issue.

---

# 28. Privacy Metrics

- data access requests
- deletion requests
- retention jobs success
- exports
- privacy incidents
- sensitive fields collected
- third-party processor inventory coverage

---

# 29. Integration Metrics

per provider:

- Connected Accounts
- Sync Success Rate
- Event Processing Lag
- Retry Rate
- Auth Failure
- Re-auth Required
- Duplicate Event Prevented
- Mapping Failure
- Last Successful Sync

---

# 30. AI Metrics

## Adoption

- AI-assisted actions
- active AI users
- feature adoption

## Quality

- draft acceptance rate
- correction rate
- clarification rate
- entity resolution accuracy
- date extraction accuracy

## Safety

- blocked unauthorized actions
- unsafe clinical requests
- prompt-injection test pass
- user override

## Cost

- AI cost per clinic
- AI cost per workflow
- transcription cost

---

# 31. Clinic Outcome Metrics

این metricها باید با احتیاط تفسیر شوند چون causality مستقیم همیشه قابل اثبات نیست.

## Operational Outcomes

- missed follow-up reduction
- overdue reduction
- manager reporting time reduction
- handoff error reduction
- workflow cycle time
- unresolved actions

## Commercial/Clinic Outcomes

در صورت data معتبر:

- rebooking
- treatment follow-up conversion
- recovered opportunity

نباید بدون baseline به TaskMG attribution قطعی داده شود.

---

# 32. Pilot Metrics

قبل از Pilot:

- baseline

در Pilot:

- adoption
- capture rate
- outcome quality
- workflow execution
- manager usage

پایان Pilot:

- before/after
- qualitative feedback
- willingness to pay
- decision

---

# 33. Pilot Scorecard

## A — Adoption

- active users
- workflow penetration

## B — Data Quality

- owner coverage
- due coverage
- outcome coverage

## C — Operational Improvement

- overdue
- follow-up delay
- status-report effort

## D — Management Value

- dashboard use
- exception management

## E — Commercial

- paid conversion
- expansion intent

---

# 34. Metric Guardrails

افزایش یک metric نباید رفتار بد ایجاد کند.

مثال:

## Task Completion Count

ممکن است user taskهای کوچک بسازد برای بالا بردن count.

پس:
completion count همراه:
- on-time rate
- workflow outcome
- reopen

دیده شود.

---

# 35. Vanity Metrics

به‌تنهایی تصمیم‌ساز نیستند:

- total registered users
- total lifetime tasks
- total messages
- AI requests
- page views

context و cohort لازم دارند.

---

# 36. Event Taxonomy

حداقل eventها:

- clinic.created
- user.invited
- user.activated
- patient.created
- case.created
- workflow.started
- task.created
- task.assigned
- task.completed
- task.overdue
- followup.created
- followup.outcome_recorded
- case.next_action_set
- dashboard.viewed
- report.exported
- integration.connected
- ai.action_drafted

---

# 37. Event Properties

هر event:

- timestamp
- organization_id
- branch_id optional
- user_id
- role
- entity_id
- workflow
- source channel
- client/version

Sensitive text در analytics event ذخیره نشود.

---

# 38. Data Quality KPIs

- events missing tenant
- tasks missing owner
- time-sensitive tasks missing due
- completed follow-up missing outcome
- active case missing next action
- orphan external links

---

# 39. Dashboard Cadence

## Daily Operations Dashboard

Audience:
manager.

Includes:
- due today
- overdue
- blocked
- escalated
- follow-up

## Weekly Business Review

- adoption
- workflow performance
- exceptions
- support
- pilot/value metrics

## Monthly Business Review

- revenue
- retention
- unit economics
- sales
- customer health

## Quarterly Strategy Review

- ICP performance
- roadmap
- pricing
- segment economics
- risk register

---

# 40. Customer Health Score

Components:

- usage
- manager activity
- workflow penetration
- support health
- payment status
- champion status
- outcome trend

نباید single black-box AI score باشد.

Transparent weighted score بهتر است.

---

# 41. Cohort Strategy

Cohortها:

- onboarding month
- segment
- plan
- clinic size
- workflow
- acquisition channel

این کمک می‌کند بفهمیم PMF در کدام Segment قوی‌تر است.

---

# 42. Metric Ownership

## Product

- activation
- workflow usage
- adoption
- product quality

## Sales

- pipeline
- win
- cycle
- CAC

## Customer Success

- health
- retention
- expansion

## Engineering

- reliability
- security operational metrics

## Finance/Founder

- MRR
- margin
- payback
- runway

---

# 43. Target Setting

Targetها باید سه نوع باشند:

## Baseline

واقعیت فعلی.

## Validation Target

برای اثبات فرضیه.

## Operating Target

بعد از داده کافی.

نباید benchmark عمومی را بدون context به Operating Target تبدیل کرد.

---

# 44. Alerting

Alert زمانی مفید است که owner و action داشته باشد.

مثال:

- integration sync failed > threshold
- overdue spike
- backup failed
- security event
- payment failure
- clinic usage collapse

---

# 45. Data Review Rules

هر KPI در review باید با این سؤال‌ها همراه باشد:

1. نسبت به baseline چه تغییری کرده؟
2. کدام segment؟
3. علت احتمالی چیست؟
4. آیا data quality خوب است؟
5. چه action می‌گیریم؟
6. چه زمانی دوباره اندازه می‌گیریم؟

---

# 46. Metrics MVP

قبل از اولین Pilot باید حتماً داشته باشیم:

- Active Users
- Task Created/Completed
- On-time Completion
- Overdue
- Follow-up Outcome
- Cases with Next Action
- Dashboard Views
- Workflow Started/Completed
- Errors
- Pilot conversion

---

# 47. Definition of Metrics Readiness

Metrics system زمانی قابل اعتماد است که:

- event definitions versioned باشند؛
- tenant scope داشته باشند؛
- duplicate event کنترل شود؛
- metric query مستند باشد؛
- dashboard و source query تطبیق داده شوند؛
- sensitive data analytics-minimized باشد.

---

# 48. تصمیم KPI فعلی

موفقیت TaskMG با «تعداد task ساخته‌شده» سنجیده نمی‌شود.

ترتیب ارزش:

**Reliable Actions → Healthy Workflows → Active Managers → Retained Clinics → Profitable Expansion**
