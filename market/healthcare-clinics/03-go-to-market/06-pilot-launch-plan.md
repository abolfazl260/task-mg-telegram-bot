# برنامه Pilot و Launch — Healthcare Clinics

> وضعیت سند: Pilot & Launch Plan v1  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> هدف: اثبات Workflow Value، Adoption و Willingness to Pay قبل از Scale.

---

# 1. هدف Pilot

Pilot برای تست Feature نیست؛ برای تست این فرضیه‌هاست:

1. frontline از سیستم در کار واقعی استفاده می‌کند؛
2. manager visibility بیشتری می‌گیرد؛
3. workflow selected outcome قابل اندازه‌گیری دارد؛
4. implementation قابل تکرار است؛
5. buyer حاضر به ادامه paid است.

---

# 2. Pilot Type

## Design Partner Pilot

برای 1 تا 3 customer اول.

ویژگی:
- feedback بالا
- scope محدود
- founder involvement
- explicit learning agreement

## Standard Pilot

بعد از تثبیت onboarding.

ویژگی:
- repeatable package
- fixed duration
- fixed workflow set
- standard review

---

# 3. انتخاب کلینیک Pilot

## Must

- ICP fit
- champion
- economic buyer
- daily workflow volume
- staff participation
- willingness to measure
- decision date

## Prefer

- manager
- treatment coordinator
- implant/prosthetic workflow
- current process fragmented
- no major integration dependency

---

# 4. Pilot Disqualification

Pilot شروع نشود اگر:

- buyer مشخص نیست
- فقط curiosity است
- انتظار replacement کامل billing/insurance/scheduling یا clinical automation بدون Scope مشخص
- custom development زیاد
- no staff commitment
- no baseline
- no success criteria
- no commercial next step

---

# 5. Pilot Scope

## Duration

Working range:
**4 تا 8 هفته**

## Users

ترجیحاً:
**5 تا 15 user**

## Workflows

فقط 2 workflow.

مثال:

### Pilot A
Treatment Plan Follow-up + General Callback

### Pilot B
Lab Case + Daily Operations

### Pilot C
Post-Treatment + Recall

---

# 6. Pilot Agreement

قبل از start ثبت شود:

- scope
- start/end
- users
- workflows
- responsibilities
- data scope
- support
- metrics
- review date
- pricing/next-step expectation

---

# 7. Commercial Commitment

Preferred:

- paid pilot
- setup fee
- or written conversion framework

Pilot رایگان فقط exception.

هدف:
جلوگیری از free consulting بدون تصمیم خرید.

---

# 8. Pre-Pilot Discovery

## Workflow Mapping

برای هر workflow:

- trigger
- current steps
- actors
- tools
- handoffs
- delays
- failure points
- desired outcome

## Output

Current-State Map + Future-State Map.

---

# 9. Baseline Collection

قبل از Go-Live:

- follow-up volume
- overdue estimate
- no-next-action cases
- manager status time
- current tool count
- response delay
- workflow completion estimate

اگر historical data نیست:
1-week observation baseline.

---

# 10. Data Scope

Pilot باید minimum data داشته باشد.

## Prefer

- synthetic training data first
- Patient Record scope defined
- identity/contact/clinical fields mapped intentionally
- Clinical Data access, audit and retention reviewed before real-data use

## Agreement

Customer بداند:
چه داده‌ای وارد می‌شود و چه داده‌ای نمی‌شود.

---

# 11. Setup

## Step 1 — Organization

- clinic
- branch
- timezone
- admin

## Step 2 — Team

- users
- roles
- permissions

## Step 3 — Patient References

- CSV import or manual limited set

## Step 4 — Workflows

2 selected templates.

## Step 5 — Rules

- owner
- due
- outcomes
- reminder
- escalation

## Step 6 — Dashboard

saved views.

---

# 12. Training

Training باید role-based باشد.

## Reception

- capture
- today
- outcome
- reschedule

## Coordinator

- follow-up queue
- next action

## Manager

- dashboard
- overdue
- escalation

## Doctor

- quick delegation
- approval

## Owner

- review metrics

---

# 13. Training Format

Recommended:

- 45-60 min manager/admin
- 20-30 min frontline
- quick reference
- in-product guidance
- first-day support

Long generic training avoid شود.

---

# 14. Go-Live Readiness Checklist

قبل از Go-Live:

- users active
- roles correct
- patient data ready
- templates tested
- reminders tested
- permissions tested
- dashboard works
- support channel clear
- baseline saved
- buyer/champion confirmed

---

# 15. Week 1

هدف:
Adoption stabilization.

Daily check:

- login/activity
- tasks captured
- incomplete workflow
- confusion
- duplicate process
- notification noise

## CS Action

fast fixes for:
- labels
- views
- training
- template configuration

نه feature build فوری برای هر request.

---

# 16. Week 2-3

هدف:
Behavior consistency.

Review:

- % workflow inside system
- overdue
- outcome completion
- manager usage
- staff feedback

اگر adoption پایین است:
root cause analysis.

---

# 17. Mid-Pilot Review

## Agenda

1. usage
2. workflow data
3. friction
4. support issues
5. baseline comparison
6. scope correction

## Decision

- continue
- narrow
- configuration fix
- terminate

Scope expansion وسط Pilot فقط اگر original objective ثابت مانده.

---

# 18. Final Review

## Presentation

### Before
current process.

### Adoption
who used.

### Workflow
volume/completion.

### Outcomes
measured change.

### Qualitative
staff/manager feedback.

### Gaps
remaining blockers.

### Recommendation
paid rollout.

---

# 19. Success Criteria

Targets اولیه، نه industry benchmark.

## Adoption

- >=70% target users active weekly
- >=70% selected workflow actions captured

## Data Quality

- >=90% tasks with owner
- >=85% time-sensitive tasks with due

## Workflow

- >=80% completed follow-ups with structured outcome
- declining no-next-action cases

## Management

- manager uses dashboard multiple times/week
- manual status process reduced

## Commercial

- paid conversion or explicit no-go decision

---

# 20. Qualitative Success

Pilot موفق اگر users بگویند:

### Reception
«کمتر چیزی را در ذهن نگه می‌دارم.»

### Manager
«برای status کمتر دنبال افراد می‌گردم.»

### Owner
«می‌دانم کجا backlog داریم.»

---

# 21. Failure Criteria

Pilot ناموفق اگر:

- system only used for demo
- staff returns to chat/spreadsheet
- manager doesn't use dashboard
- data entry creates more work
- workflow cannot fit without heavy custom code
- buyer sees no value
- security scope cannot be met

---

# 22. Pilot Metrics Dashboard

## Adoption

- active users
- tasks/user
- Telegram actions
- Web actions

## Workflow

- created
- completed
- overdue
- outcome rate
- next action rate

## Manager

- dashboard views
- escalations
- backlog trend

---

# 23. Support During Pilot

Response priority:

## P0
access/security/data issue.

## P1
workflow blocked.

## P2
usability/configuration.

## P3
feature request.

Feature requests جدا track شوند؛ support queue را تبدیل به roadmap نکنند.

---

# 24. Pilot Feedback

Channels:

- weekly manager call
- frontline mini interviews
- in-product issue capture
- final survey

Question:
«اگر TaskMG فردا حذف شود، چه چیزی دوباره سخت می‌شود؟»

---

# 25. Feature Request Handling

هر request:

- role
- problem
- frequency
- workaround
- impact
- segment relevance

باید ثبت شود.

No instant commitment.

---

# 26. Conversion to Paid

قبل از پایان Pilot:

- pricing already discussed
- decision date scheduled
- buyer invited
- proposal draft ready

## Review Outcome

### Success
Paid rollout.

### Partial
Scoped extension only with reason.

### Fail
Close and document learning.

---

# 27. Paid Rollout

بعد از conversion:

- contract
- subscription
- final workflow config
- data migration
- broader training
- success plan

Pilot configuration نباید undocumented production setup شود.

---

# 28. Case Study Capture

در صورت رضایت customer:

- baseline
- workflow
- measured outcome
- quote
- screenshots with safe data

Consent explicit.

---

# 29. Launch Readiness

Market launch بعد از:

- 3+ completed pilots
- 2+ paid customers
- 1-2 case studies
- repeatable onboarding
- stable pricing hypothesis
- core security tests
- support process
- sales playbook
- demo environment

---

# 30. Private Beta

قبل از public launch:

- limited clinic count
- high-touch support
- feature flags
- issue monitoring

هدف:
reliability.

---

# 31. Launch Positioning

Launch message:

**Clinic Operations & Follow-up Platform**

نه:
"all-in-one dental software".

---

# 32. Launch Assets

- landing page
- demo video
- workflow audit
- case study
- pricing overview
- security one-pager
- onboarding overview
- FAQ

---

# 33. Launch Channels

اولویت:

1. existing network
2. referral
3. partner
4. founder content
5. targeted search/content
6. selective event

Paid scale بعداً.

---

# 34. Launch Funnel

Visitor  
→ Workflow Audit/Demo  
→ Discovery  
→ Demo  
→ Pilot  
→ Paid

هر stage instrumentation داشته باشد.

---

# 35. Product Launch Metrics

- qualified demo requests
- demo-to-pilot
- pilot-to-paid
- activation
- 30/60/90-day retention
- support load
- onboarding time

---

# 36. Launch Risk Register

## Risk
Product instability.

Mitigation:
limited cohort.

## Risk
Wrong messaging.

Mitigation:
discovery tracking.

## Risk
Support overload.

Mitigation:
pilot limit.

## Risk
Custom requests.

Mitigation:
scope policy.

## Risk
Security concern.

Mitigation:
documentation + testing.

---

# 37. Rollback / Incident Readiness

قبل از real customer:

- backups
- restore test
- incident contact
- status communication
- audit
- logs

---

# 38. Pilot Learning Repository

برای هر Pilot:

- customer profile
- workflow
- baseline
- configuration
- issues
- requests
- outcomes
- conversion
- lessons

تا pattern بین customers دیده شود.

---

# 39. Scale Gate

پس از launch، sales scale فقط اگر:

- onboarding repeatable
- retention healthy
- support manageable
- win reason understood
- churn reason understood
- product reliable

---

# 40. Final Pilot Principle

**Pilot باید یک تصمیم تولید کند.**

نه:
«جالب بود، بعداً صحبت می‌کنیم.»

بلکه:

**Paid Rollout / Explicit No-Go / Specific Product Gap**

هر Pilot بدون Decision Framework، یادگیری و commercial discipline را ضعیف می‌کند.
