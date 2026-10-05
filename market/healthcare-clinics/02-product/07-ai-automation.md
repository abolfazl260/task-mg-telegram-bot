# AI و Automation — Healthcare Clinics

> وضعیت سند: AI Product Strategy v1  
> اصل: **AI باید اصطکاک عملیات را کم کند، نه اینکه قضاوت بالینی را جایگزین کند.**  
> دامنه اولیه: Operational AI برای Task، Follow-up، Workflow و Reporting

---

# 1. نقش AI در محصول

AI در TaskMG باید یک **Operational Copilot** باشد.

هدف AI:

- تبدیل زبان طبیعی به action ساختاریافته؛
- کاهش data entry؛
- خلاصه‌سازی backlog؛
- پیشنهاد Next Action؛
- تشخیص exception؛
- کمک به manager برای فهم وضعیت؛
- کمک به ساخت workflow.

هدف AI نیست:

- تشخیص بیماری؛
- تصمیم درمانی؛
- نسخه‌نویسی؛
- توصیه medication؛
- تغییر خودکار clinical plan؛
- پاسخ‌گویی پزشکی مستقل به بیمار.

---

# 2. AI Product Thesis

Workflow باید قبل از AI تعریف شود.

فرمول:

**Structured Workflow + Reliable Data + Permission Context + AI Assistance = Useful Operational AI**

بدون workflow ساختاریافته، AI فقط متن بیشتری تولید می‌کند.

---

# 3. سطح‌بندی Automation

## Level 0 — No AI

Rule-based automation.

مثال:
Task overdue → reminder.

## Level 1 — Read & Summarize

AI فقط می‌خواند و خلاصه می‌کند.

مثال:
«کارهای عقب‌افتاده امروز را خلاصه کن.»

## Level 2 — Suggest

AI پیشنهاد می‌دهد.

مثال:
«بهتر است برای این case یک follow-up سه‌روزه ساخته شود.»

## Level 3 — Draft Action

AI action draft می‌سازد اما اجرا نیازمند confirmation است.

مثال:
پیام → task draft.

## Level 4 — Autonomous Low-Risk Action

فقط برای actionهای کاملاً محدود و کم‌ریسک، بعد از validation.

مثال احتمالی:
تولید reminder داخلی طبق rule.

## Forbidden Autonomous Scope

- clinical decision
- treatment recommendation
- patient-facing medical advice
- access/permission change
- destructive data action بدون confirmation

---

# 4. Natural Language Task Creation

## P0/P1

User:
«فردا ساعت ۱۰ با خانم احمدی درباره ایمپلنت تماس بگیر.»

AI باید استخراج کند:

- action_type = follow_up
- title
- due
- patient candidate
- category
- owner candidate
- priority candidate

## Confirmation

قبل از create نهایی اگر ambiguity وجود دارد:

- patient
- date
- owner

باید تأیید شود.

## Acceptance

AI نباید patient اشتباه را بدون confirmation لینک کند.

---

# 5. Voice-to-Task

## نقش

برای doctor، reception و manager که typing friction دارند.

Pipeline:

Voice  
→ transcription  
→ intent extraction  
→ entity extraction  
→ permission check  
→ draft  
→ confirmation  
→ action

## Supported Intents

- create task
- create follow-up
- reschedule
- assign
- add comment
- mark outcome

## Error Handling

اگر transcription confidence یا entity resolution پایین است:
- draft نشان داده شود؛
- auto-execute نشود.

---

# 6. AI Case Summary

## Use Case

Manager یا doctor می‌خواهد سریع بفهمد:

- چه اتفاقی افتاده؟
- آخرین action چه بوده؟
- blocker چیست؟
- next action چیست؟

## Input

فقط data مجاز user:

- activity log
- task status
- comments
- outcomes
- workflow stage

## Output

ساختار پیشنهادی:

- Current Status
- Last Action
- Open Issues
- Next Action
- Due
- Owner

## Guardrail

Clinical interpretation از noteها انجام نشود مگر scope آینده با validation جدا.

---

# 7. پیشنهاد Follow-up

AI می‌تواند بر اساس workflow پیشنهاد دهد:

- follow-up لازم است؟
- چه templateای؟
- چه زمان پیشنهادی؟
- چه ownerای؟

اما timing باید از:
- configured workflow
- clinic policy

بیاید، نه invention مدل.

---

# 8. تشخیص کارهای عقب‌افتاده

این قابلیت در درجه اول rule-based است.

## Rule Engine

- due < now
- status != completed
- waiting timeout
- case no next action

## نقش AI

AI می‌تواند:
- cluster کند؛
- summarize کند؛
- severity explanation بدهد؛
- manager brief بسازد.

AI نباید source of truth برای overdue باشد.

---

# 9. Manager Brief

## Daily Brief

مثال:

- 8 کار overdue
- 3 follow-up بدون outcome
- 2 lab case در risk
- 4 case بدون next action
- 1 urgent complaint

## Priority

AI باید exception را از noise جدا کند.

## Output

- Summary
- Top Risks
- Suggested Review Order
- Links to source objects

هر claim باید traceable به data object باشد.

---

# 10. Natural-Language Reporting

Manager:

«کدام workflow این هفته بیشترین تاخیر را داشت؟»

System:

NL Query  
→ permission-aware structured query  
→ metrics  
→ AI explanation

## Rule

AI نباید عدد را از context حدس بزند.

Metric باید از database/report service بیاید.

---

# 11. Prioritization Assistance

AI می‌تواند priority recommendation بدهد با استفاده از:

- due
- workflow SLA
- current status
- blocker
- configured business importance

## Not Allowed

AI از اطلاعات بالینی حساس برای «ارزش بیمار» یا تبعیض ناموجه استفاده نکند.

---

# 12. Workflow Recommendation

Manager می‌تواند process فعلی را توضیح دهد.

AI پیشنهاد دهد:

- stages
- owner roles
- due rules
- outcomes
- escalations

## Example

«هر بیمار ایمپلنت بعد consultation باید 2 روز بعد تماس شود...»

→ draft workflow template.

## Requirement

Manager باید قبل از publish approve کند.

---

# 13. Internal Team Q&A

AI می‌تواند به سؤال‌های operational پاسخ دهد:

- امروز چه کارهایی دارم؟
- کدام taskها overdue هستند؟
- این case دست چه کسی است؟
- آخرین outcome چه بوده؟

## Permission

AI فقط همان dataای را ببیند که user در UI مجاز به دیدنش است.

**AI permission ≠ super-admin permission**

---

# 14. Patient-facing AI

## MVP

**Not Included**

دلیل:

- medical safety
- identity
- privacy
- consent
- escalation complexity

## Future

فقط برای use caseهای غیرکلینیکی محدود مثل:

- appointment logistics
- office hours
- non-medical status

با policy و review جدا.

---

# 15. Human-in-the-Loop Model

## Read-only

No confirmation required.

مثال:
summary.

## Suggestion

User accepts/rejects.

## Draft Action

Confirmation required.

## Sensitive Action

Explicit confirmation + permission.

## Destructive Action

Strong confirmation / potentially admin-only.

---

# 16. Permission-aware AI

قبل از هر tool/action:

1. identify user
2. identify tenant
3. identify role
4. check permission
5. scope data query
6. execute or deny
7. audit

Prompt instruction به‌تنهایی authorization نیست.

Backend permission check اجباری است.

---

# 17. AI Action Schema

AI نباید arbitrary code یا arbitrary database operation تولید کند.

Allowed actions به schema محدود شوند.

مثال:

- task.create
- task.assign
- task.reschedule
- task.comment
- followup.create
- followup.outcome
- report.query

هر action:

- validated arguments
- permission check
- audit

---

# 18. Structured Output

Model output برای action باید structured باشد.

Example concept:

- intent
- target_entity
- patient_reference
- owner
- due
- outcome
- confidence
- clarification_needed

Free-form text مستقیماً به write operation تبدیل نشود.

---

# 19. Entity Resolution

## Problem

نام بیمار ممکن است duplicate باشد.

## Rule

اگر چند candidate:
- AI list candidates
- user selects

اگر confidence پایین:
- no auto-link

Identifiers بر name matching ترجیح دارند.

---

# 20. Date / Time Resolution

AI باید:

- clinic timezone بداند
- relative dates را resolve کند
- ambiguity را flag کند

مثال:
«پنجشنبه» اگر context مبهم است، confirmation.

Storage:
timezone-aware timestamp.

---

# 21. Prompt Injection Risk

Comments، attachments یا external messages ممکن است متن مخرب داشته باشند.

## Rule

External content = data, not instruction.

AI agent نباید از patient note دستور tool execution بگیرد.

## Controls

- separate system instructions
- tool allowlist
- permission checks
- untrusted-content labeling
- confirmation for writes

---

# 22. Data Minimization

AI context فقط data لازم را دریافت کند.

## Avoid

- entire patient history
- unrelated cases
- full database dump
- unnecessary attachments

## Prefer

task-scoped / case-scoped context.

---

# 23. Sensitive Data Handling

قبل از ارسال data به AI provider باید بررسی شود:

- provider terms
- storage policy
- region
- retention
- customer agreement
- applicable law
- minimum necessary data

این موضوع باید per deployment/jurisdiction ارزیابی شود.

---

# 24. Logging

AI logs نباید بدون نیاز شامل raw sensitive text باشند.

Log پیشنهادی:

- request ID
- user ID/internal reference
- action type
- model/provider
- latency
- success/failure
- confirmation
- token/cost metrics

Raw prompt logging باید policy مشخص داشته باشد.

---

# 25. Audit

برای AI-generated write:

- AI initiated
- user confirmed
- final arguments
- result
- timestamp
- model/version reference where appropriate

قابل بازسازی باشد.

---

# 26. Guardrails

## Clinical

AI نباید:
- diagnose
- prescribe
- recommend medication
- alter treatment plan
- tell patient urgent clinical advice independently

## Operational

AI نباید:
- assign outside scope
- expose another branch
- export data without permission
- delete records autonomously

## Communication

patient-facing message اگر در آینده فعال شد:
- template/policy
- human review for sensitive context
- opt-out/consent

---

# 27. Failure Modes

## Hallucinated Patient

Mitigation:
entity lookup + confirmation.

## Wrong Date

Mitigation:
timezone + clarification.

## Wrong Owner

Mitigation:
role-aware candidate list.

## Fabricated Metric

Mitigation:
structured report query.

## Overconfident Summary

Mitigation:
link to source objects.

## Prompt Injection

Mitigation:
untrusted data separation.

## Data Leakage

Mitigation:
backend authorization + scoped retrieval.

---

# 28. Confidence Strategy

Confidence فقط یک عدد مدل نیست.

Decision باید بر اساس:

- unique entity match
- valid date parse
- permission
- required fields
- workflow rule

باشد.

اگر requirement ناقص:
clarification.

---

# 29. Evaluation Framework

AI قبل از production باید eval داشته باشد.

## Task Creation Eval

- intent accuracy
- patient match
- due date accuracy
- owner accuracy
- no unauthorized action

## Summary Eval

- factual consistency
- no fabricated status
- correct next action
- source traceability

## Report Eval

- numeric accuracy
- filter accuracy
- permission accuracy

## Safety Eval

- clinical request refusal/redirect
- cross-user data leakage
- prompt injection
- destructive action

---

# 30. Golden Dataset

یک مجموعه test case anonymized/synthetic ساخته شود:

- Persian task requests
- English task requests
- mixed language
- relative dates
- duplicate names
- unclear owner
- clinical vs operational request
- malicious embedded instructions

---

# 31. AI Metrics

## Product

- AI-assisted tasks created
- acceptance rate
- edit-before-confirm rate
- time saved estimate
- weekly AI users

## Quality

- extraction accuracy
- clarification rate
- action failure rate
- correction rate

## Safety

- unauthorized action blocked
- unsafe clinical request rate
- data-scope violation
- injection test pass rate

---

# 32. Cost Management

AI cost باید per tenant قابل مشاهده باشد.

- request volume
- tokens
- transcription cost
- model tier
- cached/reused result where safe

High-cost model فقط برای use caseی که value دارد.

---

# 33. Model Strategy

Provider abstraction ترجیح دارد.

Use caseها می‌توانند model requirement متفاوت داشته باشند:

## Lightweight
- intent extraction
- classification

## Stronger
- complex workflow draft
- manager summary

## Speech
- transcription

Vendor lock-in باید تا حد ممکن محدود شود.

---

# 34. Rule Engine vs AI

از AI استفاده نکن اگر rule deterministic است.

## Rule Engine

- overdue
- SLA
- recurrence
- permission
- branch scope
- escalation threshold

## AI

- language understanding
- summarization
- suggestion
- fuzzy classification

---

# 35. AI Roadmap

## Phase AI-0

No AI required for MVP core.

## Phase AI-1

- natural-language task draft
- voice-to-task
- daily summary

## Phase AI-2

- next action suggestion
- workflow draft
- manager brief

## Phase AI-3

- natural-language analytics
- risk summarization

## Phase AI-4

- low-risk autonomous operational action with strict rules

---

# 36. Automation Engine

Automation بدون AI باید first-class باشد.

Trigger:

- task status
- outcome
- time
- external event
- case state

Condition:

- role
- workflow
- priority
- branch

Action:

- create task
- assign
- remind
- escalate
- change stage
- notify

---

# 37. Automation Example — No Answer

Trigger:
Follow-up outcome = No Answer

Condition:
attempt < max_attempts

Action:
create next follow-up after configured delay.

No AI needed.

---

# 38. Automation Example — Case Without Next Action

Trigger:
case updated

Condition:
case active AND no next action

Action:
flag manager.

No AI needed.

---

# 39. Automation Example — Lab Risk

Trigger:
time check

Condition:
lab expected date passed AND status not received

Action:
notify owner + escalate.

---

# 40. Automation Example — AI-enhanced Manager Brief

Rule engine collects:

- overdue
- blocked
- escalated
- no-next-action

AI:

summarizes priority and patterns.

---

# 41. User Experience

AI نباید chat-only باشد.

AI باید داخل workflow ظاهر شود:

- quick draft
- suggestion chip
- summary card
- manager brief
- voice capture

---

# 42. AI Transparency

برای AI-generated content مشخص باشد:

- suggested by AI
- needs confirmation
- source data
- last updated

User نباید AI guess را با database fact اشتباه بگیرد.

---

# 43. Error UX

اگر AI unavailable:

Core workflow باید همچنان کار کند.

**AI failure must not block task management.**

Fallback:

- manual task form
- deterministic filters
- standard report

---

# 44. AI Acceptance Criteria

AI capability Production-ready است اگر:

1. permission-aware باشد.
2. action schema محدود داشته باشد.
3. confirmation rule مشخص باشد.
4. eval dataset داشته باشد.
5. unsafe clinical scope blocked باشد.
6. logging/audit داشته باشد.
7. failure fallback داشته باشد.
8. metric داشته باشد.
9. sensitive data policy مشخص باشد.
10. user correction آسان باشد.

---

# 45. تصمیم AI فعلی

اولویت:

**AI for Capture → AI for Summary → AI for Suggestion → AI for Analytics**

نه:

**AI for Clinical Decisions**

ارزش AI در Vertical کلینیک باید با کاهش زمان ثبت، کاهش فراموشی و افزایش وضوح عملیات سنجیده شود.
