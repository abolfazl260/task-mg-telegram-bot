# Onboarding مشتری — Healthcare Clinics

> وضعیت سند: Customer Onboarding v1  
> هدف: رساندن کلینیک از قرارداد/آمادگی خرید به اولین Workflow واقعی و پایدار با کمترین friction ممکن.

---

# 1. هدف Onboarding

Onboarding موفق یعنی:

- customer setup شده؛
- users نقش خود را می‌دانند؛
- 1-2 workflow واقعی فعال شده؛
- frontline در کار روزانه استفاده می‌کند؛
- manager dashboard را می‌بیند؛
- first value در هفته اول ایجاد شده است.

Onboarding صرفاً account creation نیست.

---

# 2. North Star Onboarding Metric

**Time to First Completed Real Workflow**

از زمان Ready شدن account تا زمانی که یک workflow واقعی customer end-to-end تکمیل شود.

Metrics مکمل:

- Time to First Task
- Time to First Follow-up
- Time to First Manager Dashboard Review
- % Users Activated
- % Selected Workflows Live

---

# 3. Onboarding Principles

1. Start small.
2. Role-based training.
3. Configure before customize.
4. Use real workflow quickly.
5. Avoid full data migration unless needed.
6. Frontline friction is critical.
7. Manager must own adoption.
8. Measure activation.

---

# 4. Pre-Onboarding

قبل از kickoff:

- contract/pilot scope confirmed
- buyer identified
- champion identified
- users list
- branches
- selected workflows
- data source
- integration needs
- security/data boundary
- success metrics
- target go-live date

---

# 5. Onboarding Owner

از سمت Customer:

- Clinic Manager / Operations Lead

از سمت TaskMG:

- Implementation / Customer Success owner

هر onboarding یک owner در دو سمت داشته باشد.

---

# 6. Kickoff Meeting

Agenda:

1. Goal
2. Workflow scope
3. Users/Roles
4. Data
5. Timeline
6. Training
7. Support
8. Success Criteria

Output:

**Onboarding Plan**

---

# 7. Clinic Setup

## Organization

- clinic name
- timezone
- locale
- language
- branding optional

## Branch

- branch name
- operating hours
- manager
- timezone override if needed

## Acceptance

Organization/Branch scope قبل از user import درست باشد.

---

# 8. Team Setup

Data:

- user
- role
- branch
- contact/account mapping
- status

## Minimum Team

- admin/owner
- manager
- reception/coordinator
- doctor/assistant as required

## Acceptance

هر user بتواند login/connect کند.

---

# 9. Role Setup

Standard role first.

- Owner
- Manager
- Doctor
- Reception
- Coordinator
- Assistant

Customization role فقط اگر gap واقعی وجود دارد.

## Permission Review

Before go-live:

- view scope
- create/edit
- assign
- reports
- admin
- export

---

# 10. Data Import

## Preferred MVP

CSV.

## Patient Data

فقط minimum operational fields.

## Validation

- duplicate check
- invalid rows
- branch mapping
- doctor mapping

## Import Report

- successful
- skipped
- failed
- reason

---

# 11. Data Minimization

قبل از import:

«آیا برای Workflow انتخاب‌شده این field لازم است؟»

اگر نه:
import نشود.

Clinical history bulk migration جزو onboarding standard نیست.

---

# 12. Workflow Setup

برای هر workflow:

- trigger
- owner role
- due rule
- outcomes
- next action
- reminder
- escalation

## Recommendation

Onboarding اولیه:
**1-2 workflow**

نه 10 workflow.

---

# 13. Template Setup

Template از library انتخاب شود.

سپس فقط این‌ها customize شوند:

- labels
- owner roles
- due intervals
- outcomes
- reminder timing
- escalation

Custom code آخرین گزینه است.

---

# 14. Workflow Dry Run

قبل از Go-Live:

یک sample case:

Trigger  
→ Task  
→ Assignment  
→ Reminder  
→ Outcome  
→ Next Action  
→ Dashboard

همه roles آن را ببینند.

---

# 15. Telegram Setup

برای frontline:

- account mapping
- start/login flow
- notification permission
- personal queue
- create/update task

## Test

هر role حداقل یک task demo انجام دهد.

---

# 16. Web Setup

برای manager/admin:

- dashboard
- saved filters
- team
- workflow views
- reports
- settings

## Test

Manager:
- overdue پیدا کند
- task reassign کند
- workflow status ببیند

---

# 17. Training Strategy

Training by Job.

## Reception

- create callback
- due
- outcome
- reschedule

## Coordinator

- follow-up queue
- next action

## Manager

- dashboard
- exception
- escalation
- reports

## Doctor

- quick delegation
- approval

## Owner

- health view

---

# 18. Training Format

## Admin / Manager

45-60 minutes.

## Frontline

20-30 minutes.

## Follow-up

15-minute office hours after go-live.

Training طولانی feature-by-feature پرهیز شود.

---

# 19. Training Assets

- one-page role guide
- 2-minute videos
- workflow card
- FAQ
- support channel
- quick commands

---

# 20. First Value

First Value examples:

### Reception
callback ثبت و به‌موقع انجام شد.

### Manager
overdue را قبل از مشکل دید.

### Owner
backlog واقعی را مشاهده کرد.

First Value باید intentional ساخته شود.

---

# 21. Go-Live

Go-Live Checklist:

- data ready
- users ready
- roles tested
- workflow tested
- reminders tested
- support ready
- dashboard ready
- baseline captured

---

# 22. Day 1

TaskMG/CS:

- check activity
- resolve access issues
- monitor workflow
- track confusion

Customer Manager:

- reinforce usage
- no parallel unofficial process if avoidable

---

# 23. First Week

Daily/near-daily monitor:

- active users
- tasks captured
- overdue
- outcomes
- user questions
- notification complaints

High-touch support acceptable.

---

# 24. Week 2

Focus changes from setup to habit.

Review:

- workflow coverage
- user adoption
- manager usage
- data quality

Training gap vs product gap جدا شود.

---

# 25. Week 4

Value Review:

- baseline
- current metrics
- qualitative feedback
- next workflows

برای Paid customer:
Success Plan update.

---

# 26. Activation Definition

Clinic Activated اگر:

1. admin setup complete
2. target users connected
3. 1 workflow live
4. first real tasks created
5. first real outcomes recorded
6. manager dashboard used

---

# 27. User Activation

Frontline Activated:

- connected
- viewed queue
- completed/updated real task

Manager Activated:

- viewed dashboard
- managed exception

---

# 28. Adoption Risks

## Risk — Double Entry

Fix:
integration/import/process redesign.

## Risk — Too Many Notifications

Fix:
digest/preferences.

## Risk — Too Many Fields

Fix:
defaults/minimal form.

## Risk — Manager Not Reinforcing

Fix:
executive alignment.

## Risk — Doctor Friction

Fix:
minimum interaction.

---

# 29. Change Management

Product adoption is process change.

Customer manager باید:

- explain why
- set expected behavior
- stop old duplicate process gradually
- review exceptions
- celebrate success

---

# 30. Parallel Process Policy

در transition ممکن است old system باقی بماند.

اما برای selected workflow باید source of action مشخص باشد.

مثال:

PMS = appointment record  
TaskMG = follow-up action

---

# 31. Implementation Customization

## Standard

configuration included.

## Custom

if customer asks new workflow:

- problem definition
- reuse potential
- effort
- pricing

قبل از build.

---

# 32. Data Quality

During onboarding check:

- duplicate patients
- missing owners
- missing due
- invalid branch
- inconsistent status

Garbage-in باعث adoption failure می‌شود.

---

# 33. Onboarding Health Score

Components:

- setup completion
- user activation
- workflow live
- task capture
- manager usage
- unresolved blockers

Color:

- Green
- Yellow
- Red

---

# 34. Red Onboarding

Trigger:

- champion inactive
- <50% target users activated
- no real workflow after first week
- repeated access issue
- major integration blocker

Action:

executive/manager reset meeting.

---

# 35. Customer Responsibilities

Customer must provide:

- staff participation
- data accuracy
- manager ownership
- timely feedback
- policy decisions
- approved workflow

TaskMG نباید مالک internal management customer شود.

---

# 36. TaskMG Responsibilities

- setup
- configuration
- training
- technical support
- onboarding metrics
- issue resolution
- best-practice guidance

---

# 37. Onboarding Documentation

Per customer store:

- configuration
- roles
- workflows
- integrations
- custom decisions
- training completed
- success criteria
- unresolved issues

---

# 38. Handoff to Customer Success

Onboarding closes when:

- activation achieved
- critical issues resolved
- production owner identified
- success metrics defined
- next review scheduled

Handoff includes full context.

---

# 39. Onboarding Metrics

- setup duration
- time to first value
- activation rate
- training attendance
- support tickets first 30 days
- workflow capture rate
- manager adoption
- onboarding CSAT

---

# 40. Onboarding Improvement Loop

Monthly review:

- longest step
- common issue
- repeated custom request
- training confusion
- data import failure

هدف:
کاهش time-to-value بدون کاهش quality.

---

# 41. Self-Service Roadmap

بعد از repeatability:

- guided setup
- role import
- template wizard
- CSV mapper
- checklist
- interactive training

اما high-touch learning زود حذف نشود.

---

# 42. Onboarding Definition of Done

Onboarding Done است وقتی:

**Customer نه فقط account دارد، بلکه workflow واقعی را با تیم واقعی اجرا می‌کند و manager می‌تواند outcome را ببیند.**
