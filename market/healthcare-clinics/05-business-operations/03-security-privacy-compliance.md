# امنیت، حریم خصوصی و Compliance — Healthcare Clinics

> وضعیت سند: Security & Privacy Strategy v1  
> دامنه: Healthcare Clinics Vertical  
> اصل: **Security and privacy are product requirements, not legal footnotes.**  
> هشدار: این سند چارچوب محصول و عملیات است و جایگزین مشاوره حقوقی تخصصی در کشور/ایالت/استان مشتری نیست.

---

# 1. هدف

TaskMG در Vertical کلینیک ممکن است با personal information و در برخی deploymentها با health information حساس سروکار داشته باشد.

هدف این سند:

- حداقل‌سازی data risk
- تعریف access model
- ایجاد auditability
- تعریف security baseline
- آماده‌سازی regulatory assessment
- جلوگیری از claimهای compliance بدون evidence

---

# 2. Compliance Position

TaskMG نباید بدون ارزیابی رسمی بگوید:

- HIPAA compliant
- GDPR compliant
- PHIPA compliant
- PIPEDA compliant
- یا هر certification مشابه

به‌جای آن:

1. jurisdiction مشخص شود؛
2. role حقوقی مشخص شود؛
3. data flow مشخص شود؛
4. gap assessment انجام شود؛
5. قرارداد و کنترل‌ها align شوند؛
6. سپس claim دقیق ساخته شود.

---

# 3. Data Classification

## Class A — Public / Non-sensitive

- public marketing content
- generic workflow template

## Class B — Internal Business

- team assignment
- internal process
- staff workload
- internal comments بدون patient context

## Class C — Personal Information

- patient name
- phone
- email
- appointment reference
- staff personal data

## Class D — Sensitive Health-related Information

- patient-linked treatment context
- health information
- clinical notes
- medical documents
- diagnosis if ever stored

## Policy

Healthcare به‌صورت رسمی Class D را نیز نگهداری می‌کند. Class D باید با کنترل سخت‌گیرانه‌تر شامل least privilege، permission مستقل، audit، retention، secure export، backup protection و incident controls مدیریت شود. Data minimization به معنی حذف Clinical Data از محصول نیست؛ به معنی جلوگیری از دسترسی/کپی/پردازش غیرضروری است.

---

# 4. Patient Record & Clinical Data Boundary

## TaskMG Healthcare باید بتواند ذخیره و مدیریت کند

- patient identity / demographics
- contact information
- allergies
- chronic conditions
- medications
- diagnoses
- medical / clinical history
- clinical notes
- treatment-related information
- medical documents / attachments
- imaging metadata/files where enabled
- doctor/branch relationships
- workflow status
- next action
- owner
- due date
- operational outcome
- external system references

## Access Rule

وجود Patient Record به معنی دسترسی یکسان همه Roleها نیست. Clinical Data باید permission-aware باشد و در صورت نیاز permissionهای read/manage جدا از `patients.view/manage` داشته باشد.

## AI / Clinical Decision Boundary

ذخیره Clinical Data داخل Scope است. موارد زیر capability جداگانه‌اند و بدون طراحی، ارزیابی و approval مستقل فعال نمی‌شوند:

- autonomous diagnosis
- autonomous prescription
- autonomous treatment recommendation
- autonomous modification of clinical plan

## Principle

**Store the patient record safely; expose only what each role needs; audit sensitive access and changes; integrate with external PMS/EMR when useful.**

---

# 5. Data Inventory

برای هر data field باید ثبت شود:

- data category
- purpose
- source
- legal/contractual basis where applicable
- retention
- users with access
- processors/subprocessors
- exportability
- deletion behavior

این Inventory باید living document باشد.

---

# 6. Data Flow Mapping

حداقل flowها:

## Patient Data

Clinic/PMS/CSV  
→ TaskMG  
→ Operational Database  
→ Telegram/Web User  
→ Audit

## AI

Authorized Operational Context  
→ AI Processing Boundary  
→ Suggested/Draft Output  
→ Human Confirmation  
→ TaskMG

## Integration

External Provider  
→ Webhook/API  
→ Normalizer  
→ Domain Event  
→ Task/Case

---

# 7. Access Control

## Core Model

RBAC + Tenant Scope + Branch Scope + Object Context.

## Authorization Order

1. authenticate user
2. identify tenant
3. validate active membership
4. validate role
5. validate branch
6. validate object scope
7. authorize action

## Critical Rule

Frontend hiding is not authorization.

تمام permissionها backend-side enforce شوند.

---

# 8. Roles & Permissions

## Owner

- organization-wide reporting
- configuration
- billing where applicable

## Manager

- branch operations
- staff workflow
- reports

## Doctor

- related operational cases
- delegation
- approvals

## Reception

- necessary patient references
- callbacks
- appointment-related operational tasks

## Coordinator

- follow-ups
- case actions

## Assistant

- assigned/related tasks

## Admin

- system configuration
- controlled privileged access

---

# 9. Least Privilege

هر Role فقط minimum access لازم را داشته باشد.

Examples:

- Reception ممکن است به full medical history نیاز نداشته باشد؛ Patient Record وجود دارد اما دسترسی باید role/permission-specific باشد.
- Doctor لزوماً integration secret را نمی‌بیند.
- Support staff نباید production patient data را default ببینند.
- AI tool نباید admin permission ضمنی داشته باشد.

---

# 10. Tenant Isolation

این مهم‌ترین invariant امنیتی SaaS است.

هر query domain:

- organization_id
- permission context

داشته باشد.

## Required Tests

- User A cannot read Patient B from another tenant
- task ID guessing blocked
- branch isolation
- attachment isolation
- search isolation
- export isolation
- AI isolation

---

# 11. Authentication

## Baseline

- secure session/token
- expiration
- revocation
- account disable
- secure password handling where passwords exist
- Telegram account mapping verification

## P1

- MFA for privileged/admin users
- suspicious login controls

## Enterprise

- SSO / SAML/OIDC where justified

---

# 12. Session Security

- secure cookie flags for web
- CSRF protection where relevant
- session rotation
- inactivity timeout
- explicit logout
- revoke on role removal
- device/session list later

---

# 13. Privileged Access

Admin/support access باید:

- explicit
- time-limited where possible
- audited
- justified

Shared admin account ممنوع.

---

# 14. Audit Log

حداقل Eventها:

- login/security event
- role change
- permission change
- patient access where required by deployment
- task change
- case change
- outcome change
- export
- integration connect/disconnect
- admin access

Audit باید:

- tamper-resistant design
- append-oriented
- tenant-scoped
- queryable

باشد.

---

# 15. Encryption

## In Transit

TLS برای:
- Web
- API
- Webhook
- integration connection

## At Rest

Database/storage encryption باید بر اساس infrastructure baseline فعال باشد.

## Application-level Protection

برای:
- OAuth tokens
- API secrets
- sensitive integration credentials

strong secret protection/encryption لازم است.

---

# 16. Secret Management

Secretها نباید در این مکان‌ها باشند:

- source code
- Git repo
- client-side bundle
- logs

استفاده از:
- environment secret
- managed secret store
- rotation

---

# 17. Logging

Structured logs:

- request ID
- user/internal actor ID
- tenant
- action
- error code

## Do Not Log by Default

- raw patient message
- medical note
- access token
- password
- API secret
- full attachment content

---

# 18. Error Handling

Client:

generic safe message.

Server:

structured detailed log.

نباید متن exception یا stack trace به client برگردد.

---

# 19. Data Minimization

هر field جدید باید Purpose Test پاس کند:

1. چرا جمع می‌شود؟
2. workflow به آن نیاز دارد؟
3. آیا external reference کافی است؟
4. چه کسی باید ببیند؟
5. چه زمانی حذف می‌شود؟

---

# 20. Purpose Limitation

Data برای یک use case جمع‌آوری شده نباید بدون assessment برای use case جدید استفاده شود.

مثال:

patient phone برای follow-up  
≠ automatically permission for marketing campaign.

---

# 21. Consent

Consent همیشه تنها legal basis نیست و قواعد jurisdiction متفاوت‌اند.

محصول باید بتواند در use caseهای لازم metadata نگه دارد:

- channel consent
- status
- captured_at
- source
- revoked_at

ولی تعیین اینکه consent در هر scenario لازم است، legal assessment است.

---

# 22. Privacy Notice Support

Customer باید بتواند توضیح دهد:

- چه dataای پردازش می‌شود
- چرا
- چه مدت
- با چه processorهایی
- چگونه request ثبت می‌شود

TaskMG باید information لازم برای این transparency را فراهم کند.

---

# 23. Data Subject / Patient Requests

بسته به jurisdiction:

- access
- correction
- export
- deletion
- restriction

ممکن است مطرح شوند.

Product باید حداقل:

- search/export capability controlled
- correction process
- deletion/retention workflow

داشته باشد.

---

# 24. Data Retention

Retention نباید infinite-by-default باشد.

Policy per category:

- active operational tasks
- closed cases
- comments
- attachments
- audit
- integration event payload
- logs

## Rule

Audit retention ممکن است از operational data متفاوت باشد.

---

# 25. Deletion

Deletion مدل‌های مختلف دارد:

- soft delete
- hard delete
- anonymize/pseudonymize
- legal hold

هر object باید policy مشخص داشته باشد.

Patient deletion نباید audit integrity را بی‌منطق بشکند.

---

# 26. Backup

حداقل:

- automated backups
- encrypted storage
- retention policy
- access control
- monitoring

Backup فقط وقتی ارزش دارد که restore قابل اعتماد باشد.

---

# 27. Recovery

باید تعریف شود:

- RPO target
- RTO target
- restore procedure
- restore owner
- test cadence

اعداد نهایی بعد از infrastructure/SLA design تعیین شوند.

---

# 28. Restore Testing

حداقل دوره‌ای:

- database restore
- attachment restore
- configuration restore

test شود.

Success/Failure مستند شود.

---

# 29. Incident Response

Incident lifecycle:

Detect  
→ Triage  
→ Contain  
→ Preserve Evidence  
→ Eradicate  
→ Recover  
→ Assess Notification Duties  
→ Customer Communication  
→ Postmortem

---

# 30. Security Incident Severity

## SEV-1

confirmed sensitive data exposure / major compromise.

## SEV-2

significant security degradation or suspected limited exposure.

## SEV-3

contained low-impact issue.

تعریف نهایی باید با company incident framework align شود.

---

# 31. Breach Assessment

برای incident privacy:

- what data
- how many records/users
- sensitivity
- unauthorized party
- duration
- containment
- harm likelihood
- applicable notification law

Legal/privacy owner باید involvement داشته باشد.

---

# 32. Vulnerability Management

- dependency scanning
- OS/container updates
- code review
- secret scanning
- security tests
- high-risk remediation SLA

Severity:
Critical / High / Medium / Low.

---

# 33. Secure SDLC

قبل از merge critical code:

- code review
- automated tests
- authorization tests
- dependency check
- migration review

Security-sensitive changes:
- permission
- auth
- export
- integrations
- AI actions

نیاز به review ویژه دارند.

---

# 34. Test Environment

Production patient data نباید default در test/staging کپی شود.

Prefer:

- synthetic data
- anonymized data
- generated clinic fixtures

---

# 35. Third-Party Risk

Vendorهای مهم:

- cloud
- database
- AI provider
- email/SMS/WhatsApp
- monitoring
- file storage
- payment

برای هر vendor:

- data processed
- location
- subprocessor
- security
- retention
- contract
- breach terms

ثبت شود.

---

# 36. AI Privacy

قبل از ارسال data به AI:

- minimum context
- provider data usage terms
- retention
- region
- contract
- opt-out/controls
- customer agreement

بررسی شود.

AI نباید context کل clinic را برای یک task دریافت کند.

---

# 37. AI Security

- tool allowlist
- backend permission
- human confirmation
- prompt injection defense
- untrusted content separation
- output validation
- audit

---

# 38. Integration Security

- OAuth state secure and expiring
- secure token storage
- webhook signature verification
- idempotency
- tenant mapping
- minimum scopes
- revoke/disconnect
- no secrets in logs

OAuth state نباید memory-only باشد اگر multi-instance/restart مطرح است.

---

# 39. File Security

- MIME/extension validation
- size limit
- storage isolation
- authorization
- malware scanning strategy
- signed/controlled download
- retention

---

# 40. Export Security

Export یکی از high-risk actionهاست.

کنترل:

- explicit permission
- tenant filter
- branch scope
- audit
- export field set
- rate/volume review

---

# 41. Regulatory Assessment — United States

اگر deployment تحت HIPAA باشد، باید مشخص شود TaskMG:

- Business Associate است یا نه؟
- PHI دریافت/نگهداری می‌کند؟
- BAA لازم است؟
- Security Rule safeguards کافی‌اند؟
- Breach Notification duties چیست؟

HHS Security Rule روی administrative، physical و technical safeguards برای confidentiality، integrity و availability اطلاعات سلامت الکترونیکی تأکید دارد.

Reference:
https://www.hhs.gov/hipaa/for-professionals/security/index.html

---

# 42. Regulatory Assessment — Canada

Canada نیازمند بررسی هم‌زمان federal و provincial scope است.

PIPEDA در بخش خصوصی روی accountability، consent، limiting collection/use، safeguards و breach obligations چارچوب دارد.

در حوزه سلامت ممکن است provincial health privacy law اعمال شود؛ برای مثال Ontario دارای PHIPA و oversight توسط IPC است.

## Product Implications

- accountability
- processor/service provider diligence
- access controls
- breach process
- consent/purpose
- safeguards
- retention

References:

- https://www.priv.gc.ca/en/privacy-topics/privacy-for-businesses/
- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda-compliance-help/guide_org/
- https://www.ipc.on.ca/

---

# 43. Regulatory Assessment — EU/EEA

اگر GDPR اعمال شود، باید نقش‌ها مشخص شوند:

- Controller
- Processor
- Subprocessor

اصول کلیدی:

- lawfulness/fairness/transparency
- purpose limitation
- data minimization
- accuracy
- storage limitation
- integrity/confidentiality
- accountability

همچنین:

- legal basis
- data subject rights
- breach notification
- processor contract
- international transfer
- DPIA where applicable

References:

- https://commission.europa.eu/law/law-topic/data-protection_en
- https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en

---

# 44. Jurisdiction Decision Gate

قبل از launch در هر کشور:

1. target country/province/state
2. entity legal role
3. data categories
4. hosting location
5. subprocessors
6. cross-border transfers
7. healthcare-specific law
8. contract requirements
9. breach process
10. deletion/access requirements

review شوند.

---

# 45. Compliance Evidence

Claim فقط با evidence.

Evidence examples:

- architecture diagram
- data inventory
- access matrix
- security policies
- test results
- audit logs
- vendor inventory
- incident plan
- backup tests
- training records
- contract templates

---

# 46. Policy Set Required

قبل از broad commercialization:

- Information Security Policy
- Access Control Policy
- Privacy Policy
- Data Retention Policy
- Incident Response Plan
- Backup/Recovery Policy
- Vendor Risk Policy
- Secure Development Policy
- AI Use Policy
- Acceptable Use Policy

---

# 47. Employee / Contractor Controls

- confidentiality agreement
- least privilege
- onboarding access
- offboarding same-day revoke
- security training
- privileged access approval

---

# 48. Customer Contract Controls

قرارداد باید روشن کند:

- data roles
- customer responsibilities
- security commitments
- support/SLA
- subprocessors
- data return/deletion
- incident communication
- acceptable use

قالب نهایی نیازمند legal review است.

---

# 49. Security Readiness Before Real Patient Data

Go-live ممنوع تا زمانی که حداقل:

- tenant isolation tested
- RBAC tested
- secrets secure
- logs safe
- backups running
- restore tested
- audit works
- exports permissioned
- production monitoring works
- incident contacts defined
- data flow documented

---

# 50. Compliance Anti-patterns

نباید:

- logo/claim compliance بدون assessment
- shared clinic accounts
- broad admin by default
- production data in development
- sensitive data in logs
- indefinite retention
- external AI with unknown data terms
- unverified webhook
- public attachment URL
- security by obscurity

---

# 51. Security KPI Set

- open Critical/High findings
- auth failures
- authorization violations
- privileged users
- stale users
- backup success
- restore test status
- audit event coverage
- dependency critical vulnerabilities
- incident MTTR

---

# 52. Ownership

## Engineering

technical controls.

## Product

data minimization and permission UX.

## Operations

incident/vendorship.

## Customer

user access and lawful use.

## Legal/Privacy Counsel

jurisdiction interpretation and contractual/legal obligations.

---

# 53. Definition of Security/Privacy Ready

Vertical زمانی برای commercial patient-linked use آماده است که:

1. data scope حداقل و مستند باشد؛
2. tenant/role isolation تست شده باشد؛
3. audit trail موجود باشد؛
4. backup/restore تست شده باشد؛
5. vendor/subprocessor inventory کامل باشد؛
6. incident response فعال باشد؛
7. customer contract/data roles مشخص باشند؛
8. jurisdiction assessment برای بازار launch انجام شده باشد.

---

# 54. تصمیم فعلی

امن‌ترین Product Strategy این است:

**Store less clinical data, integrate with the clinical system of record, enforce tenant/role boundaries, and make every sensitive action auditable.**

Compliance یک Feature checkbox نیست؛ ترکیبی از Product، Infrastructure، Operations، Contracts و Jurisdiction است.
