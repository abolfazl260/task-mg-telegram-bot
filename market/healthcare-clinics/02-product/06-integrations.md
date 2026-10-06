# Integration Strategy — Healthcare Clinics

> وضعیت سند: Integration Strategy v1  
> اصل: **Integrate where it removes duplicate work, creates reliable triggers, or closes the outcome loop.**  
> هدف: اتصال optional TaskMG Clinic به سیستم‌های خارجی و Communication Channelها، بدون ایجاد وابستگی محصول به آنها.

---

# 1. نقش Integration در Product

TaskMG باید System of Action باشد، نه System of Record.

بنابراین Integration سه کار اصلی دارد:

1. **Inbound Event**  
   یک اتفاق در سیستم خارجی، workflow یا task بسازد.

2. **Context Sync**  
   context لازم را بدون ورود دستی تکراری وارد کند.

3. **Outcome Sync**  
   نتیجه action را در صورت نیاز به سیستم اصلی برگرداند.

مثال:

Appointment marked No-show in PMS  
→ Event وارد TaskMG  
→ Recovery Follow-up Task  
→ Reception calls patient  
→ Outcome = Rebooked  
→ optional sync back.

---

# 2. Integration Principles

## Principle 1 — Business Outcome First

هیچ connector صرفاً برای اینکه «Integration داریم» ساخته نشود.

سؤال:

**این Integration کدام manual step را حذف می‌کند؟**

---

## Principle 2 — Prefer Reference over Replication

اگر سیستم خارجی مالک داده است، TaskMG تا حد امکان external ID و minimal context نگه دارد.

---

## Principle 3 — Idempotency

یک event خارجی نباید دو task یکسان تولید کند.

هر inbound event باید:
- provider
- external event ID
- idempotency key
- processed state

داشته باشد.

---

## Principle 4 — Webhook First, Polling as Fallback

اگر provider webhook/change notification معتبر دارد، event-driven sync ترجیح دارد.

Polling فقط برای:
- provider بدون webhook
- recovery
- reconciliation

---

## Principle 5 — Sync Is Eventually Consistent

TaskMG نباید فرض کند external event delivery همیشه کامل و فوری است.

Reconciliation لازم است.

---

## Principle 6 — Least Privilege

OAuth scope فقط به حد لازم محدود شود.

---

## Principle 7 — No Sensitive Data in Tokens/URLs

secret، PHI یا patient detail در webhook token، query string یا log ذخیره نشود.

---

# 3. Integration Architecture

مدل پیشنهادی:

External Provider  
→ Connector Adapter  
→ Event Normalizer  
→ Idempotency Check  
→ Domain Event  
→ Workflow Engine  
→ Task / Case / Follow-up  
→ Outcome  
→ Optional Outbound Sync

---

# 4. Integration Objects

## IntegrationConnection

- id
- tenant_id
- provider
- account_reference
- auth_type
- status
- scopes
- token_reference
- expires_at
- last_sync_at
- created_at

## ExternalObjectLink

- tenant_id
- provider
- object_type
- external_id
- internal_type
- internal_id
- sync_state
- last_seen_at

## ExternalEvent

- provider
- external_event_id
- event_type
- received_at
- processed_at
- status
- retry_count

## SyncCursor

- provider
- resource
- cursor/token
- updated_at

---

# 5. Telegram

## وضعیت

Telegram هسته Execution Channel فعلی TaskMG است.

## Role

- task capture
- reminders
- quick status
- comments
- voice input
- approvals
- personal queue

## P0

- bot interaction
- callback actions
- notification delivery

## P1

- deep links to Web
- message-to-task
- richer role-specific UX

## Security

- user mapping
- bot/tenant scope
- callback authorization
- no sensitive data in callback payload

---

# 6. Calendar Integration

Calendar integration نباید TaskMG را به scheduling engine کامل تبدیل کند.

## Use Cases

- appointment event reference
- cancellation event
- no-show trigger if source supports status
- follow-up after event
- pre-appointment checklist
- doctor schedule context

---

# 7. Google Calendar

Google Calendar API از event resources، incremental sync و watch/push notification پشتیبانی می‌کند.

## P1 Use Cases

- read selected calendar events
- map event → appointment reference
- detect event change
- create internal action

## Architecture

Google Event  
→ ExternalObjectLink  
→ appointment reference  
→ workflow event

## Push Notifications

Google Calendar watch channels می‌توانند change notification به HTTPS webhook ارسال کنند. Delivery باید به‌عنوان signal در نظر گرفته شود و reconciliation باقی بماند.

## Security

- OAuth per user/service account strategy بررسی شود
- minimum Calendar scope
- refresh-token protection
- notification channel expiration renewal
- no patient-sensitive data in channel token

## Official References

- https://developers.google.com/workspace/calendar/api/v3/reference/events
- https://developers.google.com/workspace/calendar/api/guides/push

---

# 8. Microsoft Outlook / Microsoft Graph

Microsoft Graph change notifications می‌تواند برای resource changes webhook ایجاد کند.

## Use Cases

- calendar event read
- event change
- internal task trigger
- synchronization

## Requirements

- delegated/application permission strategy
- subscription renewal
- webhook validation
- lifecycle handling

## Official References

- https://learn.microsoft.com/en-us/graph/api/resources/change-notifications-api-overview
- https://learn.microsoft.com/en-us/graph/change-notifications-overview

---

# 9. Existing Clinic Software / PMS

این Integration می‌تواند duplicate entry را کم کند، اما پیش‌نیاز Clinic نیست. Patient Record و Session management باید داخل TaskMG مستقل کار کنند.

## Strategy

### Level 0 — CSV
شروع ساده برای Pilot.

### Level 1 — Scheduled Import
اگر provider export منظم دارد.

### Level 2 — REST API
برای providerهای پرتکرار.

### Level 3 — Event/Webhook
اگر سیستم پشتیبانی کند.

## Data We Want

حداقل:

- patient external ID
- display name
- appointment reference
- doctor
- branch
- selected operational status/event

## Clinical Data Integration Rule

Clinical data بخشی از Patient Record در TaskMG است و می‌تواند از PMS/EMR وارد یا با آن sync شود. Integration باید field mapping، source metadata، permission، audit، conflict policy و idempotency مشخص داشته باشد.

از sync بدون قاعده یا انتقال داده بدون purpose/permission جلوگیری شود؛ نه از خود Clinical Data.

---

# 10. FHIR / Healthcare Standards

FHIR فقط زمانی ارزش دارد که target system واقعاً FHIR interface داشته باشد.

طبق HL7، FHIR R5 نسخه منتشرشده current است و R6 در سال 2026 همچنان در مسیر توسعه/انتشار قرار دارد؛ بنابراین connector production نباید بر draft behavior بدون نیاز واقعی وابسته شود.

## Relevant Resource Concepts

در صورت نیاز:

- Patient
- Practitioner
- Organization
- Appointment
- Task
- ServiceRequest
- Encounter

## Strategy

TaskMG نباید «FHIR-first» شود.

برای SMB dental clinics اغلب:
- vendor API
- CSV
- calendar
- webhook

عملی‌تر هستند.

FHIR برای:
- enterprise clinic
- health network
- interoperable medical system

ارزش بیشتری دارد.

## Official Reference

- https://hl7.org/fhir/

---

# 11. SMS

## Use Cases

- patient reminder
- follow-up notification
- confirmation request

## Product Principle

SMS provider باید abstraction باشد.

Interface:

- send_message
- delivery_status
- inbound_message optional

## Requirements

- consent
- opt-out
- template policy
- delivery status
- per-country compliance review
- cost tracking

## P1/P2

بسته به Pilot و جغرافیا.

---

# 12. WhatsApp

## Use Cases

- patient follow-up
- reminder
- inbound response
- approved template message

## Strategy

WhatsApp را channel بدانیم، نه database.

Patient response:

External Message  
→ normalized event  
→ linked patient/case  
→ task/outcome suggestion  
→ human action

## Requirements

- provider/business account setup
- template rules
- consent
- webhook verification
- conversation cost tracking
- jurisdiction review

## Priority

P1/P2 بر اساس market.

---

# 13. Email

## Use Cases

- lab communication
- referral communication
- manager digest
- external notifications

## P1

- outbound email notification
- inbound email-to-task برای use case محدود

## Risks

- email thread parsing
- attachment safety
- sensitive content
- duplicate thread events

---

# 14. Laboratory Integration

## Near-term

نیازی به full lab system integration در MVP نیست.

## MVP

- lab name
- external reference
- expected date
- manual status

## P2

اگر الگوی تکراری بین چند customer دیده شد:

- case sent
- received
- status update
- delivery reference

## Build Rule

فقط برای lab/vendor پرتکرار connector اختصاصی بسازیم.

---

# 15. Accounting Integration

## Use Cases محدود

- payment status trigger
- invoice reference
- financial hold marker

## Not Goal

TaskMG حسابداری نمی‌شود.

## P2

تنها اگر workflowهای operational به financial status وابسته شوند.

---

# 16. Payment Integration

## Use Cases

- payment received → next operational action
- deposit received → schedule/preparation workflow
- failed payment → follow-up

## Data Principle

payment provider مالک اطلاعات کارت و تراکنش حساس است.

TaskMG فقط:
- payment reference
- status
- amount if needed
- timestamp

را نگه دارد.

---

# 17. API Strategy

TaskMG باید API داخلی تمیز قبل از ecosystem گسترده داشته باشد.

## Core API Domains

- patients/references
- cases
- tasks/actions
- follow-ups
- workflows
- users/roles
- reports
- integrations

## Requirements

- tenant scope
- authorization
- pagination
- filtering
- idempotency for create
- versioning
- audit

---

# 18. Webhook Strategy

## Outbound Webhooks

Events:

- task.created
- task.completed
- task.overdue
- followup.completed
- case.stage_changed
- case.needs_attention

## Requirements

- signed requests
- delivery ID
- retry
- timeout
- exponential backoff
- dead-letter state
- replay protection

## Inbound Webhooks

- provider verification
- signature check
- idempotency
- raw event retention policy
- normalization

---

# 19. Import / Export

## P0 Import

CSV.

### Patient Record / Patient Work Item
- external_id
- name
- phone optional
- doctor
- branch

### Task
فقط برای migration خاص.

## P0 Export

- tasks
- follow-ups
- workflow outcomes
- reports

## Requirements

- tenant-scoped
- role permission
- export audit
- UTF-8
- timezone clarity

---

# 20. Sync Direction Strategy

هر connector باید یکی از این modeها داشته باشد:

## Read-only Inbound
بهترین برای شروع.

## Outbound-only
برای notification/action.

## Bidirectional
فقط وقتی conflict model تعریف شده.

## Recommendation

Pilot integrations را read-only یا event-inbound شروع کنیم.

Bidirectional sync complexity را زود وارد نکنیم.

---

# 21. Conflict Resolution

اگر TaskMG و external source یک field را تغییر دهند، باید source-of-truth مشخص باشد.

مثال:

Appointment time:
**Source of truth is configurable. TaskMG Clinic can be the primary patient/session record; PMS/Calendar may be an integrated external source when enabled.**

Task outcome:
**TaskMG = source of truth**

نباید Last Write Wins کورکورانه استفاده شود.

---

# 22. Timezone Handling

Integration باید:

- timestamps را با timezone/UTC استاندارد ذخیره کند
- clinic timezone داشته باشد
- provider timezone را map کند
- DST edge case را تست کند

---

# 23. Retry Strategy

Transient error:

- exponential backoff
- bounded retry
- jitter where appropriate

Permanent error:

- failed state
- operator visibility

Authentication error:

- connection needs re-auth

---

# 24. Reconciliation

Webhook به‌تنهایی کافی نیست.

Periodic reconciliation:

- missing event detection
- stale link detection
- expired subscription detection

Google Calendar documentation نیز هشدار می‌دهد notification delivery کاملاً قابل تضمین نیست؛ طراحی باید missing notification را تحمل کند.

---

# 25. OAuth Strategy

## Requirements

- state with expiration
- one-time use
- secure storage
- token encryption/protection
- refresh handling
- revocation
- provider+tenant+user mapping

## Multi-instance

OAuth state نباید صرفاً در memory process نگهداری شود.

---

# 26. Integration Observability

برای هر provider:

- connection status
- last successful sync
- last error
- retry count
- event lag
- webhook health
- token expiration
- objects synced

---

# 27. Integration Security Checklist

- signature verification
- TLS
- minimum scopes
- secret rotation
- no raw secrets in logs
- tenant mapping check
- external ID validation
- idempotency
- rate limit handling
- audit

---

# 28. Integration Priority Matrix

| Integration | User Value | Sales Impact | Complexity | Priority |
|---|---:|---:|---:|---|
| Telegram | Very High | High | Existing | P0 |
| CSV Import/Export | High | High | Low | P0 |
| Internal API/Webhook | High | High | Medium | P0/P1 |
| Google Calendar | High | Medium | Medium | P1 |
| Outlook Calendar | High | Medium | Medium | P1 |
| Clinic PMS Generic API | Very High | High | High | P1 |
| Email | Medium | Medium | Medium | P1 |
| SMS | High | High | Medium | P1/P2 |
| WhatsApp | High | High | Medium-High | P1/P2 |
| Lab Connector | Medium | Medium | High | P2 |
| Payment | Medium | Medium | Medium | P2 |
| Accounting | Low-Medium | Low | High | P2 |
| FHIR | High for enterprise | Low for SMB | High | P2/Enterprise |

---

# 29. Connector Build Decision

یک connector اختصاصی فقط اگر یکی از این شروط برقرار باشد:

1. حداقل چند customer آن را می‌خواهند.
2. blocker فروش جدی است.
3. duplicate data entry زیادی حذف می‌کند.
4. event با ارزش بالا تولید می‌کند.
5. provider API پایدار دارد.

---

# 30. Integration MVP

برای Clinic MVP:

## Required
- Telegram
- CSV import/export
- internal webhook/API foundation

## Optional Pilot
- Calendar connector فقط اگر workflow Pilot نیاز دارد

## Not Required
- PMS deep sync
- WhatsApp
- lab
- accounting
- FHIR

---

# 31. Existing Core Reuse

پروژه فعلی already integration concepts برای Jira و Google/Microsoft providerها دارد.

برای Vertical باید reuse شود:

- connection model
- OAuth patterns
- provider abstraction
- external object linking
- sync idempotency lessons

اما domain mapping باید clinic-specific شود.

---

# 32. Integration Acceptance Criteria

یک Integration زمانی Production-ready است که:

1. tenant-safe باشد.
2. auth lifecycle مشخص باشد.
3. retry/idempotency داشته باشد.
4. missing event را recover کند.
5. external/internal IDs audit شوند.
6. metrics/health داشته باشد.
7. data mapping documented باشد.
8. source-of-truth defined باشد.
9. failure user-visible باشد.
10. disconnect/revoke flow داشته باشد.

---

# 33. منابع رسمی

- HL7 FHIR: https://hl7.org/fhir/
- FHIR version directory: https://hl7.org/fhir/directory.html
- Google Calendar Events API: https://developers.google.com/workspace/calendar/api/v3/reference/events
- Google Calendar Push Notifications: https://developers.google.com/workspace/calendar/api/guides/push
- Microsoft Graph Change Notifications: https://learn.microsoft.com/en-us/graph/api/resources/change-notifications-api-overview
- Microsoft Graph Notification Setup: https://learn.microsoft.com/en-us/graph/change-notifications-overview

---

# 34. تصمیم Integration فعلی

**MVP = Telegram + Import/Export + clean integration foundation.**

سپس:

**Calendar → Repeated PMS API Demand → Patient Communication Channels → Enterprise Interoperability**

Integration roadmap نباید قبل از اثبات Workflow PMF، تیم را به ساخت connectorهای متعدد منحرف کند.
