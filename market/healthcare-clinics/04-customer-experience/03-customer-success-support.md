# Customer Success و Support — Healthcare Clinics

> وضعیت سند: Customer Success & Support v1  
> هدف: حفظ سلامت operational customer، حل سریع blockerها، تبدیل support data به product learning و جلوگیری از dependency ناسالم به تیم TaskMG.

---

# 1. تفاوت Customer Success و Support

## Support

پاسخ به:
- error
- access issue
- workflow blocked
- how-to

## Customer Success

پاسخ به:
- آیا customer به outcome می‌رسد؟
- adoption سالم است؟
- manager value می‌بیند؟
- renewal risk چیست؟
- expansion opportunity چیست؟

Support reactive است؛ CS proactive.

---

# 2. Customer Success Mission

**کمک به کلینیک برای تبدیل TaskMG به workflow operational قابل اعتماد، بدون اینکه TaskMG جای manager داخلی را بگیرد.**

---

# 3. Support Model

## Standard Support

- knowledge base
- email/chat/ticket
- business-hours response
- product guidance

## Priority Support

- faster response target
- onboarding sessions
- priority escalation

## Enterprise

- negotiated SLA
- named success contact
- incident communication process

---

# 4. Support Channels

Recommended:

- in-product support/contact
- email/ticket
- Telegram support channel for controlled cases
- scheduled call for complex issue

## Avoid

Support scattered across personal staff accounts.

هر issue باید قابل track باشد.

---

# 5. Ticket Categories

- Access/Auth
- Permission
- Task/Workflow
- Reminder
- Notification
- Reporting
- Import/Export
- Integration
- Data
- Performance
- Bug
- How-To
- Feature Request
- Security/Privacy

---

# 6. Severity Model

## SEV-1 — Critical

Examples:
- widespread outage
- suspected data leak
- cross-tenant access
- data corruption
- critical workflow completely unavailable

Action:
immediate escalation.

## SEV-2 — High

- major feature unavailable
- workflow blocked for clinic
- integration outage with operational impact

## SEV-3 — Medium

- degraded behavior
- workaround exists
- limited users

## SEV-4 — Low

- question
- cosmetic
- feature request

---

# 7. SLA Strategy

تا قبل از operational maturity، SLA قراردادی aggressive داده نشود.

Internal targets تعریف شوند.

## Example Internal Targets

### SEV-1
acknowledge as fast as operationally possible; active incident handling.

### SEV-2
same business period priority.

### SEV-3
standard queue.

### SEV-4
planned response.

External SLA باید بر capacity واقعی بنا شود.

---

# 8. Incident Handling

Flow:

Detect  
→ Triage  
→ Severity  
→ Owner  
→ Contain  
→ Communicate  
→ Resolve  
→ Verify  
→ Postmortem

---

# 9. Incident Communication

Customer-facing update باید:

- fact-based
- no speculation
- impact
- current status
- workaround if safe
- next update

داشته باشد.

---

# 10. Security Incident

اگر احتمال data exposure:

- restrict access
- preserve evidence
- incident owner
- legal/privacy assessment
- customer communication according to applicable obligations

Security incident مثل normal bug ticket مدیریت نشود.

---

# 11. Support Context

Ticket باید automatically/explicitly context داشته باشد:

- organization
- user
- role
- branch
- entity IDs
- request/error ID
- timestamp
- version/build

بدون اینکه sensitive data unnecessary log شود.

---

# 12. Error IDs

User-facing generic error:

«عملیات انجام نشد. Error ID: XYZ»

Internal:
structured logs.

Raw stack/exception به customer نشان داده نشود.

---

# 13. Knowledge Base

Sections:

1. Getting Started
2. Roles
3. Tasks
4. Follow-ups
5. Workflows
6. Dashboard
7. Telegram
8. Integrations
9. Reports
10. Security/Privacy FAQ
11. Troubleshooting

---

# 14. Knowledge Base Principle

Article باید Job-based باشد.

بد:
"Task Settings Reference"

بهتر:
"چطور Follow-up بدون پاسخ را برای روز بعد تنظیم کنیم؟"

---

# 15. Training

## New Customer

role-based onboarding.

## New Employee

short role guide.

## New Feature

use-case training.

## Manager

workflow/report best practices.

---

# 16. Office Hours

برای early customers:

weekly/biweekly optional office hours.

هدف:

- questions
- patterns
- adoption issues

نه انجام کارهای روزمره customer به جای manager.

---

# 17. Success Reviews

## 30-Day

- activation
- workflow usage
- friction

## 60/90-Day

- outcomes
- adoption
- optimization

## Quarterly for Larger Accounts

- business goals
- metrics
- risks
- expansion

---

# 18. Success Review Template

1. Goals
2. Usage
3. Workflow Metrics
4. Outcome
5. Issues
6. Feedback
7. Recommendations
8. Next Actions
9. Owners
10. Review Date

---

# 19. Customer Health Score

Example:

## Adoption — 30%

- WAU
- workflow coverage

## Value — 25%

- outcome metrics

## Manager Engagement — 20%

- dashboard/review

## Product Health — 15%

- bugs/integration

## Relationship — 10%

- champion/sponsor

Weights hypothesis هستند.

---

# 20. Health Score Status

## Green

- core usage healthy
- manager active
- no critical blocker

## Yellow

- decline
- unresolved issues
- champion risk

## Red

- core workflow stopped
- cancellation
- major product blocker
- no sponsor

---

# 21. Green Playbook

- normal review
- collect proof
- identify expansion
- ask referral when value clear

---

# 22. Yellow Playbook

- contact champion
- diagnose root cause
- simplify workflow
- training/configuration
- assign recovery actions
- recheck in defined period

---

# 23. Red Playbook

- executive escalation
- critical issue plan
- commercial transparency
- clear save/no-save decision

Avoid endless rescue cycle.

---

# 24. Escalation Paths

## Product Bug

Support → Engineering.

## Workflow Design

Support/CS → Implementation/Product.

## Commercial

CS → Sales/Account owner.

## Security

Immediate Security/Technical owner.

---

# 25. Support-to-Product Loop

Support issue tags aggregate شوند.

Monthly:

- top ticket category
- repeated confusion
- bug frequency
- workflow friction
- documentation gap

Product تصمیم بگیرد:
fix / UX / docs / training.

---

# 26. Feature Requests

Support agent نباید promise بدهد.

Response:

- understand problem
- capture use case
- record frequency/impact
- product review

---

# 27. Feature Request Schema

- customer
- persona
- problem
- current workaround
- frequency
- severity
- business impact
- requested solution
- segment
- revenue/retention risk

---

# 28. Support Metrics

- ticket volume
- tickets/account
- first response
- resolution time
- reopen rate
- escalation rate
- bug rate
- CSAT

---

# 29. Success Metrics

- activation
- health distribution
- renewal
- churn
- expansion
- adoption
- time-to-value

---

# 30. Support Load as Product Metric

اگر ticket volume per active clinic بالا می‌رود:

ممکن است نشان‌دهنده:
- UX problem
- reliability
- onboarding gap
- configuration complexity

باشد.

---

# 31. Customer Effort

بعد از key support interaction:

«حل این مشکل چقدر آسان بود؟»

Customer Effort می‌تواند برای workflow product مفید باشد.

---

# 32. CSAT

CSAT فقط support friendliness نیست.

می‌توان segment کرد:

- onboarding
- support
- product
- training

---

# 33. NPS

NPS در sample کوچک early stage noisy است.

استفاده شود اما تصمیم اصلی بر:

- retention
- adoption
- outcome
- qualitative interviews

باشد.

---

# 34. Support Permissions

Support staff access باید controlled باشد.

Principles:

- least privilege
- customer consent/process where necessary
- audit
- temporary elevated access
- no shared credentials

---

# 35. Support Data Privacy

Ticket ممکن است sensitive info داشته باشد.

Guidance:

- request minimum
- redact
- secure channel
- avoid patient detail in screenshots where possible

---

# 36. Remote Assistance

اگر future remote/admin access وجود داشت:

- explicit approval
- time-limited
- logged
- scoped

---

# 37. Customer Success Segmentation

## High-touch

- pilot
- multi-branch
- enterprise
- high-risk

## Tech-touch

- stable small clinics
- mature onboarding

## Low-touch

فقط بعد از product maturity.

---

# 38. CSM Portfolio

در future، account load بر اساس:

- complexity
- ARR
- support load
- onboarding need

تعیین شود، نه فقط customer count.

---

# 39. Implementation vs Support

Support نباید دائماً custom workflow design رایگان انجام دهد.

اگر درخواست:
- project work
- integration
- data migration
- custom report

است، Professional Services process داشته باشد.

---

# 40. Customer Communication Cadence

## Operational

incident/support.

## Educational

feature/use case.

## Success

review/value.

## Commercial

renewal/expansion.

Channelها قاطی نشوند.

---

# 41. Status Page

بعد از customer base واقعی:

- service health
- major incident
- maintenance

باعث کاهش duplicate tickets می‌شود.

---

# 42. Maintenance Communication

Planned maintenance:

- advance notice
- affected functions
- window
- expected impact
- completion notice

---

# 43. Release Notes

Release note user-facing:

- what changed
- who benefits
- action required

نه internal technical changelog.

---

# 44. Customer Success Playbook

## New Customer
Onboarding.

## Activated
Adoption.

## Healthy
Value/Expansion.

## Yellow
Recovery.

## Red
Executive Save.

## Renewal
Value Review.

## Churn
Exit Interview + Data Export/Offboarding.

---

# 45. Offboarding

اگر customer leaves:

- confirm cancellation
- export process
- retention/deletion policy
- revoke integrations
- remove access
- final invoice
- exit feedback

Transparent offboarding trust را بالا می‌برد.

---

# 46. Customer Advocacy

پس از proven value:

- testimonial
- case study
- referral
- reference

No pressure.

---

# 47. Definition of Excellent Support

Support عالی یعنی فقط پاسخ سریع نیست.

یعنی:

**مشکل customer با context درست حل شود، علت تکرار شناسایی شود، data امن بماند و learning به Product برگردد.**

---

# 48. Final CS Principle

Customer Success owner نتیجه customer است، اما customer manager owner process داخلی خود باقی می‌ماند.

TaskMG باید **enable** کند، نه اینکه به outsourced operations team تبدیل شود.
