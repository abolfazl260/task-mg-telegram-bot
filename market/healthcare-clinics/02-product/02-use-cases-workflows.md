# Use Caseها و Workflowهای اصلی — Healthcare Clinics

> وضعیت سند: Product Workflow v1  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> هدف: تعریف workflowهای واقعی که Product باید پشتیبانی کند و مشخص‌کردن اولویت MVP، trigger، نقش‌ها، statusها و outcome هر جریان.

---

# 1. اصل طراحی Workflow

Workflow در TaskMG نباید صرفاً یک لیست task باشد. هر workflow باید حداقل این اجزا را داشته باشد:

- Trigger
- Context
- Owner
- Due Date / SLA
- Status
- Required Outcome
- Next Action
- Escalation
- Audit Trail

مدل پایه:

**Event → Action → Owner → Due → Outcome → Next Action**

---

# 2. اولویت‌بندی Workflowها

## P0 — MVP Critical
1. Treatment Plan Follow-up
2. Patient Callback / General Follow-up
3. Lab Case Tracking
4. Post-Treatment Follow-up
5. Daily Operations Tasks

## P1 — Early Expansion
6. Missed Appointment / No-show Recovery
7. Recall / Periodic Return
8. Multi-step Treatment Coordination
9. Internal Request / Doctor-to-Staff Delegation
10. Complaint Handling
11. Shift Handoff

## P2 — Scale
12. Result / Document Follow-up
13. Referral Tracking
14. Staff Onboarding
15. Inventory Action Workflow
16. Marketing Lead Follow-up
17. Multi-branch Operations

---

# 3. Use Case 1 — Treatment Plan Follow-up

## Problem

بیمار consultation یا examination شده و treatment plan دریافت کرده، اما درمان هنوز شروع نشده است. اگر next action مشخص نباشد، patient opportunity می‌تواند از pipeline خارج شود.

## Trigger

- treatment plan ثبت شد؛
- consultation پایان یافت؛
- patient گفت «بعداً تصمیم می‌گیرم»؛
- estimate ارسال شد؛
- financing/payment discussion pending.

## Actors

- Dentist / Doctor
- Treatment Coordinator
- Reception
- Manager

## Primary Owner

Patient Coordinator یا Reception.

## Data / Context

حداقل:

- patient reference؛
- treatment category؛
- responsible doctor؛
- consultation date؛
- current status؛
- next action date؛
- last outcome.

در MVP از ذخیره clinical detail غیرضروری اجتناب شود.

## Workflow

### Step 1 — Create Follow-up
سیستم یا کاربر task ایجاد می‌کند.

Status: **New**

### Step 2 — First Contact
Owner تماس می‌گیرد.

Possible Outcomes:
- Accepted
- Needs Time
- No Answer
- Declined
- Wants New Consultation
- Financial Concern
- Other

### Step 3A — Accepted
Next Action:
booking / internal handoff.

Status: **Converted / Handoff**

### Step 3B — Needs Time
Follow-up date جدید.

Status: **Follow-up Scheduled**

### Step 3C — No Answer
- retry schedule؛
- max attempts policy.

### Step 3D — Declined
reason ثبت شود.

Status: **Closed - Lost**

## Escalation

اگر:
- due date گذشت؛
- چند attempt بدون outcome؛
- high-value case بدون next action؛

→ manager flag.

## Success Metrics

- % treatment plans with next action؛
- follow-up completion rate؛
- median time to first follow-up؛
- no-next-action count؛
- outcome distribution.

## MVP Fit

**P0 — بسیار بالا**

---

# 4. Use Case 2 — General Patient Callback

## Problem

بیمار تماس یا پیام می‌دهد و پاسخ نهایی در همان لحظه ممکن نیست.

مثال:
- «دکتر باید جواب بدهد.»
- «بعداً تماس بگیرید.»
- «نتیجه را بررسی می‌کنیم.»
- «قیمت را اطلاع می‌دهیم.»

## Trigger

- inbound call؛
- Telegram/WhatsApp message؛
- front desk conversation؛
- doctor request.

## Owner

Reception / Coordinator.

## Workflow

1. Capture callback.
2. Select patient.
3. Reason category.
4. Set owner.
5. Set due time.
6. Complete with outcome.
7. If unresolved → new next action.

## Quick Capture Requirement

این flow باید در کمتر از چند interaction قابل ثبت باشد.

Example:

«تماس با خانم رضایی فردا ساعت ۱۰ بابت ایمپلنت»

سیستم باید بتواند پیشنهاد دهد:
- title؛
- due؛
- category؛
- patient context.

## Outcomes

- Resolved
- No Answer
- Reassigned
- Needs Doctor
- Follow-up Again
- Closed

## Metric

- overdue callback rate؛
- response delay؛
- callback volume.

## MVP Fit

**P0**

---

# 5. Use Case 3 — Lab Case Tracking

## Problem

Case بین کلینیک و لابراتوار چند handoff دارد و delay یا ambiguity آسان است.

## Examples

- crown؛
- bridge؛
- denture؛
- implant prosthetic؛
- aligner؛
- appliance.

## Trigger

case به lab ارسال شد.

## Actors

- Doctor
- Assistant
- Reception
- Lab
- Manager

## Core Stages

1. To Send
2. Sent to Lab
3. In Progress
4. Expected
5. Received
6. Needs Review
7. Ready for Patient
8. Completed
9. Issue / Rework

## Required Context

- patient reference؛
- doctor؛
- lab؛
- send date؛
- expected date؛
- appointment dependency؛
- attachment/reference if needed.

## Rules

### Rule 1
Expected date نزدیک شد → reminder.

### Rule 2
Expected date گذشت → owner + manager.

### Rule 3
Received → create review task.

### Rule 4
Approved → notify reception to confirm patient appointment if relevant.

## Risk Flag

اگر appointment قبل از lab expected date است:

**Schedule Risk**

## Metrics

- lab turnaround time؛
- overdue lab cases؛
- rework count؛
- appointment-at-risk count.

## MVP Fit

**P0**

---

# 6. Use Case 4 — Post-Treatment Follow-up

## Problem

پس از برخی درمان‌ها، تماس یا بررسی کوتاه لازم است اما در شلوغی فراموش می‌شود.

## Trigger

selected treatment completed.

## Example Treatments

- extraction؛
- implant surgery؛
- complex procedure؛
- treatment defined by clinic policy.

## Workflow

Treatment Completed  
→ Auto/Create Follow-up  
→ Due after configurable time  
→ Contact Patient  
→ Outcome  
→ Escalate if concern

## Outcomes

- Doing Well
- Mild Concern
- Needs Doctor Review
- Urgent Escalation
- No Answer

## Safety Rule

سیستم نباید clinical diagnosis بدهد.

اگر symptom/concern flag شود:

→ Human review.

## Metrics

- post-treatment follow-up completion؛
- time to follow-up؛
- escalation count.

## MVP Fit

**P0**

---

# 7. Use Case 5 — Daily Operations Checklist

## Problem

کارهای روزانه مثل opening، closing، equipment check یا administrative preparation ممکن است شخص‌محور باشند.

## Trigger

daily schedule / shift start.

## Examples

### Opening
- check rooms؛
- confirm supplies؛
- review day exceptions؛
- urgent callbacks.

### Closing
- open tasks reviewed؛
- tomorrow priority list؛
- handoff؛
- unresolved patient action.

## Actors

- Reception
- Assistant
- Manager

## Workflow

Recurring Template  
→ Tasks Generated  
→ Assigned by Role  
→ Complete  
→ Exception Escalated

## Metrics

- checklist completion rate؛
- late completion؛
- repeated exception.

## MVP Fit

**P0**

---

# 8. Use Case 6 — Missed Appointment / No-show Recovery

## Problem

No-show فقط calendar event نیست؛ نیاز به action دارد.

## Trigger

appointment = no-show/cancelled late.

## Workflow

No-show  
→ recovery task  
→ contact  
→ outcome

## Outcomes

- Rebooked
- No Answer
- Not Interested
- Call Later
- Invalid Contact
- Other

## Automation

No Answer:

→ retry after configurable interval.

## Metrics

- no-show recovery rate؛
- time to contact؛
- rebooking rate.

## Dependency

appointment/PMS integration ارزش زیادی دارد.

## Priority

**P1**

---

# 9. Use Case 7 — Recall / Periodic Return

## Problem

Patient باید در دوره بعدی برای check-up/cleaning/maintenance برگردد.

## Trigger

- treatment complete؛
- manual recall date؛
- PMS recall event.

## Workflow

Recall Due  
→ queue  
→ contact  
→ outcome  
→ next action / rebook.

## Status

- Due
- Contacted
- No Answer
- Scheduled
- Snoozed
- Not Interested
- Closed

## Metrics

- recall contacted؛
- scheduled؛
- overdue recall؛
- attempts.

## Priority

**P1**

---

# 10. Use Case 8 — Multi-step Treatment Coordination

## Problem

درمان چندمرحله‌ای فقط appointment sequence نیست؛ بین مراحل ممکن است prerequisite، lab، payment، imaging یا approval وجود داشته باشد.

## Example — Implant Operational Flow

Consultation  
→ imaging/action  
→ review  
→ surgery preparation  
→ surgery  
→ post-op follow-up  
→ integration period  
→ prosthetic lab stage  
→ delivery  
→ recall.

## Important Boundary

TaskMG clinical treatment plan را تعیین نمی‌کند.

فقط operational milestones را track می‌کند.

## Object

**Case**

## Case Fields

- patient reference؛
- doctor؛
- workflow template؛
- current stage؛
- next action؛
- owner؛
- due؛
- blocker.

## Metrics

- stage cycle time؛
- blocked cases؛
- no-next-action case؛
- overdue milestones.

## Priority

**P1**

---

# 11. Use Case 9 — Doctor-to-Staff Delegation

## Problem

پزشک در طول روز درخواست‌های کوتاه زیادی می‌دهد و staff باید بعداً انجام دهد.

## Example

- «به بیمار X زنگ بزنید.»
- «lab را پیگیری کنید.»
- «برای سه‌شنبه هماهنگ کنید.»
- «این case را بعداً به من یادآوری کنید.»

## UX

پزشک نباید فرم طولانی پر کند.

### Preferred
- voice؛
- quick command؛
- forward/message to bot.

## Workflow

Doctor instruction  
→ parse  
→ owner suggested  
→ due suggested  
→ confirmation  
→ task.

## Metric

- time to delegate؛
- clarification rate؛
- completion.

## Priority

**P1**

---

# 12. Use Case 10 — Complaint / Service Recovery

## Problem

شکایت بیمار اگر در chat باقی بماند ممکن است ownership مشخص نداشته باشد.

## Trigger

complaint received.

## Workflow

Complaint  
→ manager owner  
→ acknowledge  
→ investigate  
→ action  
→ patient response  
→ resolution.

## Required Fields

- category؛
- channel؛
- owner؛
- severity؛
- due؛
- outcome.

## Escalation

Urgent:

→ manager immediately.

## Metric

- time to first response؛
- resolution time؛
- open complaints.

## Priority

**P1**

---

# 13. Use Case 11 — Shift Handoff

## Problem

شیفت تمام می‌شود ولی کارهای باز باقی می‌مانند.

## Workflow

Before shift end:
- open tasks grouped؛
- due soon؛
- blocked؛
- urgent.

Outgoing staff:
- add context؛
- reassign if required.

Incoming staff:
- acknowledge handoff.

## Metric

- unacknowledged handoff؛
- overdue after handoff؛
- reassignment count.

## Priority

**P1**

---

# 14. Use Case 12 — Result / Document Follow-up

## Applicable To

مطب پزشکان و برخی dental workflows.

## Trigger

document/test/image expected.

## Workflow

Requested  
→ waiting  
→ received  
→ review assigned  
→ patient contact/action.

## Safety Boundary

TaskMG نتیجه را clinically interpret نمی‌کند مگر در آینده با controlled approved workflow.

## Priority

**P1/P2 بسته به vertical**

---

# 15. Use Case 13 — Referral Tracking

## Trigger

patient referred:
- to specialist؛
- from another provider؛
- external service.

## Workflow

Referral Created  
→ appointment/action  
→ status  
→ follow-up.

## Metrics

- open referrals؛
- time to action؛
- closed loop rate.

## Priority

**P2**

---

# 16. Use Case 14 — Staff Onboarding Workflow

## Trigger

new employee.

## Template

- account creation؛
- access؛
- policy reading؛
- training؛
- role checklist؛
- manager review.

## Value

Vertical core can expand beyond patient operations.

## Priority

**P2**

---

# 17. Use Case 15 — Inventory Action Workflow

## Boundary

TaskMG inventory ERP نیست.

اما می‌تواند action workflow را پوشش دهد.

## Example

item below threshold  
→ create procurement task  
→ assign  
→ order  
→ receive  
→ close.

## Priority

**P2**

---

# 18. Use Case 16 — Lead / Inquiry Follow-up

## Important for

- implant centers؛
- beauty clinic؛
- high-ticket treatment.

## Trigger

new inquiry.

## Workflow

New Lead  
→ first contact  
→ consultation booking  
→ attended  
→ treatment plan  
→ follow-up.

## Boundary

در Dental MVP:

CRM-light.

در Beauty expansion:

ممکن است core شود.

## Priority

**P1 Dental / P0 Beauty**

---

# 19. Use Case 17 — Multi-Branch Operations

## Problem

با اضافه‌شدن شعبه، workflowها، گزارش‌ها و ownership می‌توانند متفاوت شوند.

## Needs

- organization hierarchy؛
- branch scope؛
- branch manager؛
- central templates؛
- local queue؛
- cross-branch reporting؛
- permissions؛
- audit.

## Example

Central operations template  
→ instantiated in Branch A / B  
→ local execution  
→ central exception view.

## Priority

**P2 / Scale**

---

# 20. Workflow Template Schema

هر template باید بتواند تعریف کند:

## Identity
- name؛
- vertical؛
- version.

## Trigger
- manual؛
- scheduled؛
- external event؛
- previous outcome.

## Steps
- task؛
- approval؛
- wait؛
- decision؛
- notification.

## Ownership
- user؛
- role؛
- previous owner؛
- manager.

## Timing
- immediate؛
- relative due؛
- fixed due؛
- business hours.

## Escalation
- reminder؛
- first escalation؛
- second escalation.

## Outcome
- allowed values؛
- required note؛
- close condition.

## Next Step
conditional rule.

---

# 21. Workflow Status Model

برای task:

- New
- Assigned
- In Progress
- Waiting
- Blocked
- Completed
- Cancelled

برای case:

- Active
- Waiting
- Blocked
- Completed
- Closed

برای follow-up:

- Due
- Contacted
- Rescheduled
- Waiting
- Completed
- Closed

نباید یک status model برای همه objectها به زور استفاده شود.

---

# 22. Outcome Model

Completion به‌تنهایی کافی نیست.

مثلاً follow-up completed می‌تواند outcome متفاوت داشته باشد:

- Patient Reached
- No Answer
- Scheduled
- Declined
- Escalated

بنابراین:

**Task Status ≠ Business Outcome**

هر workflow مهم باید outcome مستقل داشته باشد.

---

# 23. Next Action Model

یکی از core differentiators.

هر active case ideally:

- next_action_type؛
- next_action_owner؛
- next_action_due؛
- next_action_status.

اگر active case بدون next action باشد:

**Attention Required**

---

# 24. Escalation Model

Escalation بر اساس workflow قابل تنظیم باشد.

## Level 0
owner reminder.

## Level 1
owner + role lead.

## Level 2
manager.

## Level 3
urgent exception.

### Rule
Escalation برای هر task لازم نیست.

---

# 25. Priority Model

پیشنهاد:

- Critical
- High
- Normal
- Low

Priority نباید جای due date را بگیرد.

---

# 26. SLA Model

برای بعضی workflowها:

- callback within X hours؛
- complaint response within Y؛
- urgent task within Z.

SLA بهتر است role/workflow-based باشد.

---

# 27. Dependencies

Workflow باید بتواند dependency داشته باشد.

مثال:

Confirm Appointment  
وابسته به:  
Lab Received

اگر prerequisite کامل نیست:

appointment-risk flag.

---

# 28. Recurring Workflows

مثال:

- opening؛
- closing؛
- weekly review؛
- monthly compliance task؛
- recall batch.

Recurring task باید template-based باشد.

---

# 29. Trigger Types

## Manual
user creates.

## Scheduled
time.

## Status-based
previous task outcome.

## External
PMS/calendar/API.

## AI-assisted
message interpreted.

---

# 30. Patient Context Strategy

Patient object در MVP lightweight باشد.

## Required
- internal reference ID؛
- display name where allowed؛
- contact reference where appropriate.

## Optional
- doctor؛
- branch؛
- tags.

## Avoid
- unnecessary clinical detail؛
- large medical record replication.

---

# 31. Case Strategy

Case برای workflowهای چندمرحله‌ای لازم است.

Examples:
- Implant Case
- Lab Case
- Complaint Case
- Treatment Follow-up Case.

Taskها زیر Case قرار می‌گیرند.

---

# 32. Role-based Queues

## Reception Queue
- callbacks؛
- appointment action؛
- handoffs.

## Coordinator Queue
- treatment follow-up؛
- no answer؛
- lead.

## Assistant Queue
- preparation؛
- lab؛
- checklist.

## Manager Queue
- overdue؛
- blocked؛
- escalated؛
- unassigned.

## Doctor Queue
- approvals؛
- review؛
- exception.

---

# 33. Daily Operational View

برای هر user:

## Today
due today.

## Overdue
past due.

## Waiting
dependent/external.

## Urgent
high priority.

## Follow-up
patient actions.

---

# 34. Manager Operational View

باید بتواند ببیند:

- overdue by owner؛
- overdue by workflow؛
- unassigned؛
- blocked؛
- due today؛
- escalated؛
- case without next action؛
- workload.

---

# 35. Owner View

کمتر detail، بیشتر trend:

- total open؛
- overdue trend؛
- follow-up completion؛
- branch comparison؛
- workflow bottleneck؛
- adoption.

---

# 36. Multi-Doctor Workflow

هر patient/case می‌تواند doctor context داشته باشد، اما action owner ممکن است staff باشد.

Example:

Doctor A patient  
→ Coordinator follow-up  
→ Manager escalation.

Permission model باید doctor context را از task owner جدا نگه دارد.

---

# 37. Multi-Branch Workflow Model

Objects:

- organization؛
- branch؛
- user scope؛
- workflow scope.

## Needs

- branch-specific queue؛
- central template؛
- local override؛
- cross-branch admin؛
- centralized reporting.

---

# 38. Cross-Branch Handoff

Example:

Patient starts at Branch A  
→ action required at Branch B.

Workflow:

- transfer context؛
- receiving owner؛
- acceptance؛
- audit.

Priority:

**Scale phase**

---

# 39. Workflow for Dental Implant — Detailed Example

## Stage 1 — Inquiry / Consultation
Action:
book consultation.

## Stage 2 — Consultation Complete
Action:
treatment follow-up.

## Stage 3 — Pre-treatment Coordination
Possible:
- imaging coordination؛
- administrative prerequisite؛
- scheduling.

## Stage 4 — Procedure Scheduled
Action:
preparation checklist.

## Stage 5 — Procedure Completed
Action:
post-treatment follow-up.

## Stage 6 — Waiting Period
Action:
future checkpoint.

## Stage 7 — Prosthetic / Lab
lab workflow.

## Stage 8 — Delivery
confirmation / completion.

## Stage 9 — Recall
future action.

### Boundary
Clinical decisions remain outside automated workflow.

---

# 40. Workflow for Orthodontics

## Trigger
case starts.

## Operational Stages
- records/admin setup؛
- appliance preparation؛
- delivery؛
- recurring visit cycle؛
- missed visit recovery؛
- treatment completion؛
- retention follow-up.

## Key Need
long-running recurring workflow.

---

# 41. Workflow for Physician Practice

## Use Case — Test Follow-up

Visit  
→ test requested  
→ waiting  
→ received  
→ doctor review  
→ patient action.

### Safety
No automated clinical interpretation.

---

# 42. Workflow for Beauty Clinic

## Lead-to-Package

Inquiry  
→ contact  
→ consultation  
→ proposal  
→ follow-up  
→ package accepted  
→ sessions  
→ rebooking/retention.

Beauty vertical requires stronger CRM pipeline.

---

# 43. Workflow for Physiotherapy

## Treatment Course

Assessment  
→ session series  
→ missed session recovery  
→ progress checkpoint  
→ rebooking  
→ discharge / future follow-up.

Key object:

course + session action.

---

# 44. Automation Examples

## Example 1
Outcome = No Answer  
→ create follow-up in 2 days.

## Example 2
Lab due tomorrow  
→ notify assistant.

## Example 3
Task overdue 24h  
→ manager escalation.

## Example 4
Case active with no next action  
→ flag.

## Example 5
Treatment completed  
→ post-op follow-up.

---

# 45. AI-Assisted Workflow Examples

## Voice
«فردا با آقای احمدی درباره پروتز تماس بگیر.»

→ task draft.

## Message
«جواب نداد، پنجشنبه دوباره تماس بگیر.»

→ current outcome + next action.

## Manager
«کارهای مهم عقب‌افتاده امروز چیست؟»

→ summarized exception report.

---

# 46. Workflow UX Requirements

## Capture
- few steps؛
- smart defaults؛
- voice.

## Execute
- clear current task؛
- one-tap outcome.

## Re-schedule
- simple.

## Escalate
- structured reason.

## Search
- patient / owner / workflow.

---

# 47. Required Audit Events

حداقل:

- created؛
- assigned؛
- reassigned؛
- due changed؛
- status changed؛
- outcome changed؛
- escalated؛
- completed؛
- reopened؛
- comment added.

---

# 48. Permission Considerations

## Reception
فقط context لازم.

## Doctor
assigned/related operational cases.

## Manager
branch-wide operational view.

## Owner
organization reporting.

## Admin
configuration.

Least privilege اصل پایه است.

---

# 49. Notification Matrix

| Event | Owner | Manager | Doctor |
|---|---|---|---|
| Assigned | Yes | No | if owner |
| Due soon | Yes | No | if relevant |
| Overdue | Yes | Conditional | Conditional |
| Escalated | Yes | Yes | if clinical action |
| Completed | Optional | Digest | Optional |
| Blocked | Yes | Conditional | if dependency |

---

# 50. Workflow Metrics

برای هر template:

- instances created؛
- completion rate؛
- median cycle time؛
- overdue rate؛
- escalation rate؛
- drop-off stage؛
- average attempts؛
- outcome distribution.

---

# 51. MVP Workflow Pack

نسخه اولیه Product باید با 5 template آماده عرضه شود:

1. Treatment Plan Follow-up
2. General Callback
3. Lab Case
4. Post-Treatment Follow-up
5. Daily Clinic Checklist

این pack باید برای Pilot کافی باشد.

---

# 52. Pilot Workflow Scope

برای هر Pilot فقط 2 workflow فعال شود.

ترتیب پیشنهادی:

### Pilot A
Treatment Plan Follow-up + General Callback

### Pilot B
Lab Case + Daily Operations

### Pilot C
Post-Treatment + Recall

هدف:

یادگیری رفتار، نه feature overload.

---

# 53. Workflow Validation Checklist

قبل از ساخت feature:

- frequency واقعی؟
- pain severity؟
- owner مشخص؟
- current workaround؟
- measurable outcome؟
- reusable across clinics؟
- required integration؟
- sensitive data؟
- frontline friction؟
- manager value؟

---

# 54. Workflow Anti-Patterns

نباید:

- برای هر customer flow کاملاً جدید code کنیم؛
- status بیش از حد بسازیم؛
- workflow را با clinical protocol یکی بدانیم؛
- هر stage را task کنیم اگر action واقعی نیست؛
- completion را outcome فرض کنیم؛
- task بدون owner بسازیم؛
- case فعال بدون next action رها کنیم.

---

# 55. Definition of Done برای یک Workflow

یک workflow زمانی Product-ready است که:

1. Trigger روشن است.
2. Actors مشخص‌اند.
3. Owner rule دارد.
4. Required context مشخص است.
5. Statusها محدود و واضح‌اند.
6. Outcome تعریف شده.
7. Next Action rule وجود دارد.
8. Reminder/escalation تعریف شده.
9. Metrics تعریف شده.
10. Privacy boundary مشخص است.
11. Template قابل reuse است.
12. Telegram و Web UX مشخص است.

---

# 56. Workflow Roadmap

## Phase 1
manual task + owner + due + reminder.

## Phase 2
patient/case context + next action.

## Phase 3
workflow template + outcomes.

## Phase 4
automation + escalation.

## Phase 5
external event integrations.

## Phase 6
AI-assisted orchestration.

---

# 57. Decision

محور توسعه Vertical نباید «صفحه بیمار» باشد.

محور توسعه باید:

**Action Workflow Around the Patient**

باشد.

Patient context لازم است، اما value اصلی از اجرای action می‌آید.

---

# 58. Product Rule نهایی

برای هر workflow جدید باید بتوان در یک جمله پاسخ داد:

**چه اتفاقی افتاده، چه کاری باید بعدش انجام شود، چه کسی مسئول است، تا چه زمانی، و اگر انجام نشد چه می‌شود؟**
