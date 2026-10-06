# ریسک‌ها و فرضیات — Healthcare Clinics

> وضعیت سند: Risk & Assumption Register v1  
> هدف: تبدیل عدم‌قطعیت‌های Market/Product/Operations به فرضیه‌های قابل آزمون و ریسک‌های دارای Owner و Mitigation.

---

# 1. Risk Management Principle

ریسک فقط چیزی نیست که «ممکن است بد شود». هر ریسک باید:

- Cause
- Event
- Impact
- Probability
- Severity
- Early Signal
- Mitigation
- Contingency
- Owner

داشته باشد.

---

# 2. Risk Scoring

## Probability

- 1 — Rare
- 2 — Unlikely
- 3 — Possible
- 4 — Likely
- 5 — Very Likely

## Impact

- 1 — Minor
- 2 — Low
- 3 — Medium
- 4 — High
- 5 — Critical

## Risk Score

**Probability × Impact**

Interpretation:

- 1–5 Low
- 6–10 Medium
- 11–15 High
- 16–25 Critical

---

# 3. Risk Register — Summary

| Risk | Probability | Impact | Score | Priority |
|---|---:|---:|---:|---|
| Weak clinic adoption | 4 | 5 | 20 | Critical |
| Product too generic | 4 | 4 | 16 | Critical |
| Overbuilding before PMF | 4 | 5 | 20 | Critical |
| Data/privacy failure | 2 | 5 | 10 | High by impact |
| Poor permission isolation | 2 | 5 | 10 | High by impact |
| Wrong ICP | 3 | 5 | 15 | High |
| Pilot does not convert | 4 | 4 | 16 | Critical |
| Integration complexity | 4 | 4 | 16 | Critical |
| Customization trap | 4 | 4 | 16 | Critical |
| Weak willingness to pay | 3 | 5 | 15 | High |
| Champion dependency | 4 | 3 | 12 | High |
| AI creates unsafe/incorrect action | 3 | 4 | 12 | High |
| Support cost too high | 3 | 4 | 12 | High |
| Competitor/PMS closes workflow gap | 3 | 4 | 12 | High |

Scores are initial working assessments and must be updated with evidence.

---

# 4. Market Risk — Wrong Beachhead

## Risk

Dental clinics may not have enough unmet workflow pain or may prefer existing PMS solutions.

## Early Signals

- interviews describe pain as minor;
- no willingness to pilot;
- customer only asks for scheduling;
- few workflows outside current PMS.

## Mitigation

- 15–20 interviews;
- shadow actual workflows;
- segment by operational complexity;
- compare small vs medium clinics;
- validate willingness to pay before build.

## Kill / Pivot Criteria

اگر چندین ICP-quality clinic نشان دهند workflow problem توسط current stack adequately solved است، Beachhead باید بازنگری شود.

---

# 5. Market Risk — Market Too Fragmented

## Risk

هر clinic process کاملاً متفاوت باشد و template reuse کم شود.

## Impact

- implementation cost بالا؛
- roadmap fragmentation؛
- low margin.

## Mitigation

- identify common 80%;
- workflow template + configuration;
- segment-specific defaults;
- reject edge-case customization.

## Indicator

% workflow steps reused across clinics.

---

# 6. Market Risk — Low Urgency

## Risk

Pain واقعی است ولی purchase urgency ندارد.

## Signals

- demo positive but no next step;
- pilot repeatedly delayed;
- no internal sponsor.

## Mitigation

- trigger-based selling;
- focus on growth/change events;
- quantify operational cost;
- fixed pilot window.

---

# 7. Product Risk — Too Generic

## Risk

TaskMG به Task Manager عمومی تبدیل شود و differentiation از ClickUp/Asana/Trello ضعیف باشد.

## Mitigation

- Patient/Case context;
- Next Action;
- Follow-up Queue;
- clinic templates;
- role-specific UX;
- clinic metrics.

## Measure

% usage through vertical workflows vs generic tasks.

---

# 8. Product Risk — Too Clinical

## Risk

گسترش Patient Record بدون permission، audit، retention و security مناسب انجام شود یا ذخیره Clinical Data با autonomous clinical decision support اشتباه گرفته شود.

## Impact

- complexity;
- compliance;
- sales expectation;
- delayed PMF.

## Mitigation

- Core typed-item/attribute boundary;
- product scope review;
- standalone-first, integrate-when-useful;
- reject clinical record expansion without evidence.

---

# 9. Product Risk — Overbuilding

## Risk

قبل از Pilot، AI/integrations/multi-branch زیاد ساخته شود.

## Mitigation

Roadmap gates:

Validate  
→ MVP  
→ Automation  
→ Reporting  
→ Integration  
→ Scale.

## Signal

high engineering output + low real clinic usage.

---

# 10. Product Risk — Workflow Too Complex

## Risk

Frontline برای ثبت task فیلد زیاد داشته باشد.

## Mitigation

- defaults;
- templates;
- Telegram;
- voice;
- minimal mandatory fields;
- usability testing.

## Metric

time-to-create-action + abandonment.

---

# 11. Adoption Risk — Staff Resistance

## Reasons

- perceived surveillance;
- extra data entry;
- change fatigue;
- unclear personal benefit.

## Mitigation

- explain user value;
- frontline co-design;
- start with 2 workflows;
- avoid punitive leaderboard;
- Telegram-first;
- champion support.

---

# 12. Adoption Risk — Doctor Friction

## Risk

اگر doctor مجبور به مدیریت task system شود، adoption پایین می‌آید.

## Mitigation

doctor UX محدود به:

- quick delegation
- approval
- exception
- voice

Manager/frontline ownership primary.

---

# 13. Adoption Risk — Notification Fatigue

## Risk

reminder زیاد → mute/ignore.

## Mitigation

- digest;
- priority-aware;
- configurable;
- quiet hours;
- escalation hierarchy.

## KPI

notification action rate / mute feedback.

---

# 14. Adoption Risk — Return to Chat

## Risk

تیم بعد از onboarding دوباره taskها را در Telegram group بدون structure مدیریت کند.

## Mitigation

- convert message→task;
- quick actions;
- manager requires structured outcomes;
- weekly workflow review.

---

# 15. Sales Risk — Long Sales Cycle

## Causes

- healthcare trust;
- software change;
- owner busy;
- security review.

## Mitigation

- narrow ICP;
- workflow audit;
- fixed demo;
- pilot package;
- clear security one-pager.

---

# 16. Sales Risk — Free Pilot Trap

## Risk

customer Pilot را استفاده می‌کند ولی buying commitment ندارد.

## Mitigation

قبل از Pilot:

- buyer identified;
- price range discussed;
- decision date;
- success criteria;
- paid/credited pilot preferred.

---

# 17. Sales Risk — Champion Leaves

## Risk

manager/coordinator champion جدا شود.

## Mitigation

- executive sponsor;
- documentation;
- multi-user value;
- owner dashboard;
- relationship mapping.

---

# 18. Pricing Risk — Underpricing

## Risk

Setup/support/integration cost بیشتر از revenue.

## Signal

high implementation hours per account.

## Mitigation

- setup fee;
- tiering;
- scope limits;
- professional services fee;
- track contribution margin.

---

# 19. Pricing Risk — Overpricing

## Risk

SMB clinic value را قبل از trust نبیند.

## Mitigation

- small landing package;
- paid pilot credited to annual;
- ROI case;
- segment-based packaging.

---

# 20. Pricing Risk — Wrong Metric

## Risk

per-user pricing باعث shared accounts یا adoption suppression شود.

## Mitigation

clinic + tier model را test کنیم.

Track:

- shared account requests;
- staff adoption;
- expansion.

---

# 21. Integration Risk — Vendor Fragmentation

## Risk

clinic software providers متعدد و APIها inconsistent باشند.

## Mitigation

- CSV first;
- generic API/webhook layer;
- connector only for repeated demand;
- external object abstraction.

---

# 22. Integration Risk — Sync Failure

## Risks

- duplicate task;
- stale appointment;
- missing event;
- wrong patient mapping.

## Mitigation

- idempotency;
- external IDs;
- reconciliation;
- retry;
- health dashboard;
- manual recovery.

---

# 23. Integration Risk — OAuth/Token Failure

## Mitigation

- persistent state;
- token refresh;
- re-auth flow;
- expiry monitoring;
- revocation.

---

# 24. Security Risk — Cross-Tenant Access

## Impact

Critical.

## Mitigation

- tenant-scoped queries;
- backend authorization;
- dedicated tests;
- code review;
- audit.

## Release Gate

No known cross-tenant issue before patient-linked production.

---

# 25. Security Risk — Shared Accounts

## Risk

clinics may use one login.

## Impact

- no accountability;
- privacy risk;
- audit useless.

## Mitigation

- easy staff onboarding;
- pricing not punishing users;
- policy;
- login controls.

---

# 26. Security Risk — Sensitive Logs

## Mitigation

- structured logging;
- redaction;
- no raw patient content;
- log review.

---

# 27. Security Risk — File Exposure

## Mitigation

- parent authorization;
- private storage;
- signed/controlled access;
- file validation;
- audit.

---

# 28. AI Risk — Hallucinated Action

## Example

AI links wrong patient or wrong date.

## Mitigation

- structured output;
- entity resolution;
- confirmation;
- confidence/ambiguity rules;
- audit.

---

# 29. AI Risk — Clinical Overreach

## Risk

user asks AI for medical recommendation.

## Mitigation

- clinical guardrails;
- operational scope;
- refusal/redirect pattern;
- evaluation suite.

---

# 30. AI Risk — Prompt Injection

## Mitigation

- treat external content as untrusted data;
- tool allowlist;
- backend authorization;
- confirmation.

---

# 31. Compliance Risk — Wrong Jurisdiction Assumption

## Risk

Product assumes HIPAA/GDPR/PIPEDA universally.

## Mitigation

- jurisdiction gate;
- legal assessment per launch market;
- contract role mapping;
- avoid compliance marketing claim until verified.

---

# 32. Compliance Risk — Overcollection

## Mitigation

- patient record model;
- data minimization review;
- clinical data boundary;
- field approval.

---

# 33. Compliance Risk — Third-party Processor

## Risk

AI/cloud/messaging vendor terms incompatible with customer obligations.

## Mitigation

- vendor inventory;
- data processing assessment;
- contract review;
- optional provider configuration.

---

# 34. Operational Risk — Support Overload

## Signal

tickets/customer remain high after first month.

## Mitigation

- templates;
- onboarding;
- knowledge base;
- product fixes;
- health score.

---

# 35. Operational Risk — Founder Dependency

## Risk

only founder can configure/sell/support.

## Mitigation

- implementation playbook;
- sales playbook;
- admin tooling;
- standardized scope;
- documentation.

---

# 36. Operational Risk — Customization Debt

## Risk

every customer gets custom behavior.

## Mitigation

Customization hierarchy:

1. Configuration
2. Template
3. Custom Field
4. Integration
5. Code only as exception

Track custom-code ratio.

---

# 37. Operational Risk — Weak Data Quality

## Symptoms

- no owner;
- no outcome;
- duplicate patient;
- missing next action.

## Mitigation

- required field by workflow;
- validation;
- data quality dashboard;
- onboarding.

---

# 38. Competitive Risk — PMS Expands

## Risk

Dental PMS adds stronger task/workflow.

## Mitigation

TaskMG differentiation باید روی:

- cross-system workflow;
- Telegram execution;
- configurable operations;
- integration;
- manager visibility

باشد.

---

# 39. Competitive Risk — Horizontal Tools

## Risk

clinic builds own workflow in ClickUp/Asana.

## Mitigation

- time-to-value;
- domain templates;
- patient/case context;
- clinic onboarding;
- low-friction UX.

---

# 40. Key Assumptions

## A1

Small/medium multi-doctor dental clinics have repeated operational actions outside PMS.

### Evidence Needed
interviews + observation.

---

## A2

Follow-up leakage is important enough to pay for.

### Evidence Needed
buyer interviews + paid pilot.

---

## A3

Telegram lowers frontline adoption friction.

### Evidence Needed
usage by channel.

---

## A4

Managers value Web visibility.

### Evidence Needed
dashboard retention.

---

## A5

Doctors prefer delegation over full workflow interaction.

### Evidence Needed
role usage.

---

## A6

Five initial workflow templates cover meaningful repeated use.

### Evidence Needed
workflow coverage.

---

## A7

Customer can start without deep PMS integration.

### Evidence Needed
pilot success with CSV/manual reference.

---

## A8

Patient Record باید بتواند اطلاعات کامل مرتبط با بیمار، از جمله Clinical Data موردنیاز، را در TaskMG نگهداری کند.

### Evidence Needed
workflow blockers.

---

## A9

Clinic + Staff Tier is an acceptable pricing structure.

### Evidence Needed
pricing interviews/deals.

---

## A10

Setup can be standardized.

### Evidence Needed
implementation hours decline across cohorts.

---

## A11

Expansion to more workflows/branches creates NRR potential.

### Evidence Needed
expansion after first workflow success.

---

## A12

AI adds convenience but is not required for core value.

### Evidence Needed
MVP success without AI dependency.

---

# 41. Assumption Evidence Levels

## Level 0 — Belief

No customer evidence.

## Level 1 — Interview

Repeated verbal evidence.

## Level 2 — Observed

Workflow observed.

## Level 3 — Behavioral

User actually uses product.

## Level 4 — Commercial

Pays/renews.

## Level 5 — Repeatable

Multiple customers repeat behavior.

Roadmap priority باید evidence level را در نظر بگیرد.

---

# 42. Assumption Validation Board

برای هر assumption:

| Field | Meaning |
|---|---|
| Assumption | what we believe |
| Importance | if wrong, what breaks |
| Evidence Level | 0–5 |
| Experiment | how to test |
| Owner | responsible person |
| Deadline | review date |
| Result | validated/refuted/uncertain |
| Decision | next action |

---

# 43. Validation Experiments

## Interview Test

برای Pain/Buyer.

## Prototype Test

برای UX.

## Concierge Test

برای workflow before automation.

## Paid Pilot

برای willingness-to-pay.

## A/B or Cohort

بعد از scale.

---

# 44. High-risk Assumption Priority

اول validate شوند:

1. Pain severity
2. Adoption
3. Willingness to pay
4. Workflow repeatability
5. Security feasibility
6. Integration necessity

بعد:

- AI
- multi-branch
- advanced reports

---

# 45. Risk Review Cadence

## Weekly During Pilot

- adoption
- bugs
- workflow risk
- security issue

## Monthly

- sales/pricing
- integration
- support
- unit economics

## Quarterly

- market
- compliance
- strategy
- competitive

---

# 46. Risk Owner Categories

- Founder/GM
- Product
- Engineering
- Security/Privacy
- Sales
- Customer Success
- Legal/External Counsel

هر Critical Risk باید named owner داشته باشد.

---

# 47. Escalation Rules

Critical risk:

- immediate review

High:

- active mitigation plan

Medium:

- monitor + scheduled action

Low:

- accept/monitor

---

# 48. Decision Log

وقتی risk accepted یا assumption validated می‌شود:

- decision
- evidence
- date
- owner
- revisit trigger

ثبت شود.

---

# 49. Kill Criteria

پروژه/feature باید متوقف یا pivot شود اگر:

- no repeated pain;
- frontline refuses use after UX iteration;
- no buyer willingness-to-pay;
- customization dominates;
- security requirement infeasible;
- integration dependency destroys unit economics;
- retention poor specifically in ICP.

Kill criteria مانع sunk-cost bias می‌شود.

---

# 50. Top Risks Right Now

با توجه به مرحله فعلی:

## 1
Adoption.

## 2
Willingness to pay.

## 3
Repeatable workflow vs custom project.

## 4
Security/tenant isolation.

## 5
Pilot-to-paid conversion.

## 6
Integration scope creep.

این شش مورد باید قبل از broad feature expansion بیشترین توجه را بگیرند.

---

# 51. تصمیم فعلی

بزرگ‌ترین ریسک TaskMG در Healthcare «کمبود Feature» نیست.

بزرگ‌ترین ریسک این است که محصول قبل از اثبات **Pain + Adoption + Willingness-to-Pay + Repeatability** بیش از حد ساخته یا سفارشی شود.

Risk management باید Roadmap را محدود و evidence-driven نگه دارد.
