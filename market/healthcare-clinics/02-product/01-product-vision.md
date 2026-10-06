# چشم‌انداز محصول — Product Vision

> وضعیت سند: Product Strategy v1  
> Vertical: Healthcare Clinics  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> Product Category: Clinic Management & Patient Record Platform

---

# 1. Product Vision

**TaskMG Healthcare باید یک Clinic Workspace مستقل باشد که Patient Record، Session/Visit history و اجرای عملیات را روی Core مشترک یکپارچه می‌کند.**

چشم‌انداز بلندمدت:

کلینیک باید بتواند بیماران، اطلاعات هویتی/تماس/بالینی، جلسات و تاریخچه آنها و همه workflowهای عملیاتی خود را در TaskMG مدیریت کند. PMS/EMR خارجی در صورت وجود optional integration است، نه پیش‌نیاز استفاده از Clinic.

---

# 2. Mission

**ایجاد یک Clinic Workspace مستقل برای نگهداری Patient Record، مدیریت Session/Visit و اجرای قابل‌اعتماد عملیات روزانه.**

ماموریت محصول سه بخش دارد:

1. Capture را سریع کند؛
2. Execution را قابل اعتماد کند؛
3. Management Visibility ایجاد کند.

---

# 3. Product Thesis

فرضیه اصلی محصول:

Clinic باید بتواند حتی بدون PMS خارجی کار کند. TaskMG باید هم Patient Record و Session history را نگهداری کند و هم بداند:
- بیمار کیست و اطلاعات تماس/بالینی او چیست؛
- چه جلساتی داشته یا خواهد داشت؛
- بعدش چه کاری باید انجام شود؛
- چه کسی انجام دهد؛
- تا چه زمانی؛
- اگر انجام نشد چه می‌شود؛
- manager و doctor کجا وضعیت را ببینند.

---

# 4. Product Promise

**Every clinic action has an owner, a due time, and a visible outcome.**

نسخه فارسی:

**هر اقدام کلینیک، مسئول، زمان و نتیجه مشخص دارد.**

---

# 5. Core Product Loop

هسته محصول:

**Capture → Context → Assign → Due → Execute → Remind → Escalate → Complete → Learn**

شرح:

## Capture
کار سریع ثبت شود.

## Context
مشخص باشد کار برای چه patient/case/workflow است.

## Assign
مالک مشخص باشد.

## Due
زمان انجام روشن باشد.

## Execute
کاربر بتواند بدون friction انجام دهد.

## Remind
قبل از فراموشی یادآوری شود.

## Escalate
اگر انجام نشد، سیستم آن را نامرئی نگذارد.

## Complete
نتیجه ثبت شود.

## Learn
مدیر از داده برای بهبود workflow استفاده کند.

---

# 6. Problem Scope

TaskMG برای این مسائل ساخته می‌شود:

- missed follow-up؛
- unclear ownership؛
- no next action؛
- operational handoff؛
- fragmented task communication؛
- overdue work؛
- weak escalation؛
- manager blindness؛
- staff dependency؛
- inconsistent process؛
- multi-branch operational visibility.

---

# 7. Non-Goals

TaskMG در این Vertical باید **Patient Record کامل و قابل توسعه** داشته باشد و بتواند اطلاعات بالینی بیمار را نگهداری کند.

مواردی که همچنان capability جداگانه محسوب می‌شوند:
- clinical decision support خودکار؛
- diagnosis خودکار توسط AI؛
- prescription خودکار؛
- treatment recommendation خودکار؛
- PACS/imaging؛
- accounting suite؛
- insurance claims؛
- payroll؛
- inventory ERP کامل؛
- full appointment engine؛
- patient portal جامع.

اصل:

**Patient Record is part of TaskMG Healthcare; external systems may integrate with it, but they do not define whether TaskMG can store the patient's record.**

---

# 8. کاربران اصلی

## 8.1 Frontline Users

### Reception / Front Desk
بیشترین capture و follow-up.

### Patient Coordinator
مدیریت next action بیمار.

### Assistant
checklist و handoff.

---

## 8.2 Operational Users

### Clinic Manager
assign، monitor، escalate، report.

### Branch Manager
کنترل local workflow.

---

## 8.3 Clinical Users

### Dentist / Doctor
delegation، approval و exception.

interaction پزشک باید حداقلی باشد.

---

## 8.4 Executive Users

### Owner
visibility و outcome.

### Multi-Branch Operations Manager
standardization و cross-branch analytics.

---

# 9. User Experience Model

محصول دو سطح UX دارد:

## Execution UX
برای frontline.

خصوصیات:
- سریع؛
- کم‌فیلد؛
- mobile-first؛
- Telegram-first؛
- action-oriented.

## Management UX
برای manager/owner.

خصوصیات:
- Web-first؛
- dashboard؛
- filters؛
- configuration؛
- reports؛
- bulk actions؛
- audit.

---

# 10. نقش Telegram

Telegram بخشی از مزیت adoption است، نه کل identity محصول.

## باید انجام دهد

- quick task capture؛
- task assignment؛
- reminder؛
- status change؛
- quick comment؛
- voice-to-task؛
- personal queue؛
- approval؛
- exception alert.

## نباید انجام دهد

- configuration پیچیده؛
- dashboard مدیریتی سنگین؛
- workflow designer؛
- reporting عمیق؛
- bulk administration.

## Product Principle

**Use Telegram for execution, not administration.**

---

# 11. نقش Web Dashboard

Web باید control plane محصول باشد.

## Core Functions

- operational dashboard؛
- backlog view؛
- overdue؛
- filters؛
- patient/case workflow context؛
- reporting؛
- team/role management؛
- template management؛
- workflow configuration؛
- branch configuration؛
- audit؛
- exports؛
- integration settings.

## Product Principle

**Use Web for visibility, management, and configuration.**

---

# 12. نقش AI

AI feature نیست؛ accelerator است.

AI باید اصطکاک workflow را کم کند.

## Priority AI Use Cases

### A1 — Natural Language Task Capture
پیام → structured task.

### A2 — Voice-to-Action
voice → title + owner + due + context.

### A3 — Daily Operational Summary
خلاصه backlog و overdue.

### A4 — Suggested Next Action
پیشنهاد action بر اساس workflow، بدون تصمیم بالینی.

### A5 — Risk Detection
شناسایی taskهای overdue یا caseهای بدون next action.

### A6 — Template Suggestion
پیشنهاد workflow قابل تکرار.

### A7 — Manager Brief
خلاصه exceptionها.

---

# 13. AI Guardrails

AI در فاز اولیه نباید:

- diagnosis دهد؛
- treatment plan بالینی تولید کند؛
- medication recommend کند؛
- clinical judgment را replace کند؛
- action حساس را بدون approval اجرا کند.

اصل:

**AI may propose operational actions; humans own clinical decisions.**

---

# 14. Product Principles

## Principle 1 — Record + Action

TaskMG Healthcare هم Patient Record را نگهداری می‌کند و هم اجرای کار را مدیریت می‌کند. هر داده بیمار باید purpose، permission، lifecycle و audit مشخص داشته باشد و هر action باید به context درست بیمار/پرونده متصل شود.

---

## Principle 2 — Minimum Data Entry

هر field اجباری باید توجیه داشته باشد.

Frontline نباید برای ساخت task فرم طولانی پر کند.

---

## Principle 3 — One Clear Owner

هر actionable work item ترجیحاً یک accountable owner داشته باشد.

---

## Principle 4 — Next Action First

برای هر case فعال باید بتوان next action را فهمید.

---

## Principle 5 — Exceptions over Noise

manager باید exceptionها را ببیند، نه هزار notification.

---

## Principle 6 — Integrate Before Replace

اگر نرم‌افزار فعلی customer یک capability را خوب انجام می‌دهد، integration اولویت دارد.

---

## Principle 7 — Workflow Before AI

AI روی process مبهم ارزش پایدار نمی‌سازد.

اول workflow؛ بعد intelligence.

---

## Principle 8 — Role-aware UX

reception، doctor و owner یک UI و notification need ندارند.

---

## Principle 9 — Privacy by Design

حداقل داده لازم، حداقل دسترسی لازم.

---

## Principle 10 — Measurable Outcomes

workflow باید metric داشته باشد.

---

# 15. Core Product Objects

برای Vertical Healthcare مدل مفهومی باید حداقل این objectها را پشتیبانی کند:

## Organization
Clinic.

## Branch
مکان عملیاتی.

## User
عضو تیم.

## Role
سطح دسترسی و مسئولیت.

## Patient / Patient Record
موجودیت اصلی بیمار و پرونده کامل قابل نگهداری او؛ شامل اطلاعات هویتی، ارتباطی، پزشکی/بالینی، اسناد، ارتباط با پزشک/شعبه، history و context عملیاتی. دسترسی به بخش‌های حساس باید permission-aware و auditable باشد.

## Case
یک موضوع یا جریان کاری مربوط به بیمار.

## Workflow
تعریف process.

## Workflow Instance
اجرای یک workflow.

## Task / Action
واحد کار.

## Follow-up
نوع action با زمان و outcome.

## Reminder
یادآوری.

## Escalation
مسیر exception.

## Comment
context تیمی.

## Attachment
فایل مرتبط.

## Event
رویدادی که workflow/action را trigger می‌کند.

## Activity Log
تاریخچه.

---

# 16. Patient Record + Action Model

TaskMG Healthcare باید هم Patient Record ماندگار و هم Action Loop را در یک مدل واحد نگهداری کند.

مدل Clinic روی Core:

**Patient (Parent Work Item / Task) → Session / Visit / Follow-up (Child Work Item / Subtask)**

هر Patient علاوه بر child itemها، Attributeهای هویتی، تماس، پزشکی و بالینی خود را دارد. هر child item نیز Attribute schema مخصوص نوع خودش را دارد.

برای actionهای اجرایی همچنان باید Current State، Next Action، Owner، Due و Outcome مشخص باشد.

در هر لحظه برای یک case فعال باید بتوان پاسخ داد:

- وضعیت چیست؟
- اقدام بعدی چیست؟
- مسئول کیست؟
- موعد چه زمانی است؟
- blocker چیست؟
- آخرین activity چیست؟

---

# 17. Workflow Engine Vision

Workflow Engine باید بتواند:

- template تعریف کند؛
- stage داشته باشد؛
- trigger داشته باشد؛
- default owner/role تعیین کند؛
- due date rule داشته باشد؛
- reminder داشته باشد؛
- escalation rule داشته باشد؛
- required outcome داشته باشد؛
- conditional next step داشته باشد؛
- audit تولید کند.

---

# 18. Template Strategy

Product باید blank canvas نباشد.

## Vertical Templates

### Dental
- treatment plan follow-up؛
- implant case؛
- lab case؛
- post-op follow-up؛
- recall؛
- missed appointment؛
- complaint؛
- daily clinic checklist.

### Physician Practice
- test result follow-up؛
- referral follow-up؛
- post-visit action.

### Beauty Clinic
- inquiry-to-consultation؛
- package follow-up؛
- session series.

### Physiotherapy
- treatment course؛
- missed session؛
- rebooking.

---

# 19. Workflow Customization Levels

## Level 1 — Template
بدون customization.

## Level 2 — Configuration
role، duration، stages، notifications.

## Level 3 — Custom Fields
فیلدهای خاص.

## Level 4 — Automation
rules و integration.

## Level 5 — Custom Development
حداقلی و فقط برای strategic account.

اصل:
**Prefer configuration over code customization.**

---

# 20. Notification Philosophy

Notification باید action-oriented باشد.

## خوب
«3 follow-up امروز overdue شده‌اند.»

## بد
notification برای هر تغییر کوچک.

### Rule
- user-level relevance؛
- urgency؛
- digest where possible؛
- escalation only when needed؛
- quiet hours؛
- configurable.

---

# 21. Reporting Philosophy

گزارش باید operational باشد.

## Frontline
- tasks today؛
- overdue؛
- follow-ups؛
- blocked.

## Manager
- backlog؛
- overdue by role؛
- completion rate؛
- workflow cycle time؛
- unassigned؛
- no-next-action cases.

## Owner
- trend؛
- branch comparison؛
- operational health؛
- adoption؛
- high-level outcomes.

---

# 22. Core Metrics

## Product Metrics
- WAU/MAU؛
- task creation؛
- task completion؛
- template use؛
- time-to-first-value.

## Workflow Metrics
- follow-up completion؛
- overdue rate؛
- time-to-action؛
- unassigned rate؛
- case without next action؛
- cycle time.

## Adoption Metrics
- % active staff؛
- % tasks captured via Telegram؛
- manager dashboard usage؛
- recurring workflow adoption.

## Business Metrics
- paid clinic count؛
- ARPA؛
- pilot-to-paid conversion؛
- retention؛
- expansion.

---

# 23. North Star Metric

North Star پیشنهادی:

**Completed On-Time Actions per Active Clinic**

چرا؟

- فقط usage نیست؛
- execution را می‌سنجد؛
- با customer value ارتباط دارد؛
- قابل segment شدن است.

Metric مکمل:

**% Active Cases with a Valid Next Action**

---

# 24. Product Success Definition

محصول موفق است اگر:

- frontline داوطلبانه استفاده کند؛
- manager به dashboard برای کار واقعی تکیه کند؛
- owner بتواند value را توضیح دهد؛
- workflow بدون founder/manual intervention اجرا شود؛
- customer تعداد workflowهای استفاده‌شده را افزایش دهد؛
- retention از habit عملیاتی ناشی شود.

---

# 25. MVP Vision

MVP باید یک سؤال را جواب دهد:

**آیا یک کلینیک می‌تواند بدون PMS/EMR اجباری، بیماران و پرونده‌هایشان را ثبت کند، Session/Visitها را مدیریت کند و عملیات روزانه را روی TaskMG اجرا کند؟**

MVP لازم نیست billing/insurance/all-in-one practice management را کامل کند، اما باید Patient Record + Session Management + Core Operations را end-to-end و مستقل پوشش دهد.

---

# 26. MVP Capability Pillars

## P1 — Action Management
- task؛
- owner؛
- due؛
- priority؛
- status.

## P2 — Follow-up
- queue؛
- reminder؛
- outcome؛
- reschedule.

## P3 — Patient Record
- Patient top-level Work Item؛
- identity/contact attributes؛
- medical/clinical attributes؛
- multiple contact points؛
- comments؛
- attachments.

## P4 — Session / Visit
- child item / subtask؛
- date/time؛
- doctor؛
- status/history؛
- clinical/session notes.

## P5 — Workflow
- templates؛
- recurring؛
- stages.

## P6 — Management
- dashboard؛
- overdue؛
- filters؛
- reports.

## P7 — Access
- roles؛
- permissions؛
- audit.

## P8 — Channels
- Telegram execution؛
- Web control.

---

# 27. MVP Exclusions

برای جلوگیری از scope creep:

- full scheduler؛
- online booking marketplace؛
- billing؛
- insurance؛
- autonomous prescription engine؛
- autonomous clinical decision/treatment recommendation engine؛
- patient mobile app؛
- full CRM suite؛
- complex inventory.

---

# 28. Product Roadmap Logic

Roadmap باید بر اساس «کاهش uncertainty» ساخته شود، نه تعداد feature.

## Phase 0 — Validate Pain
مصاحبه و workflow observation.

## Phase 1 — Prove Action Loop
Capture → assign → due → complete.

## Phase 2 — Prove Follow-up
queue + next action + reminder.

## Phase 3 — Prove Management Value
dashboard + exception.

## Phase 4 — Prove Repeatability
templates + onboarding.

## Phase 5 — Integrate
PMS/calendar/messaging.

## Phase 6 — Scale
multi-branch + advanced analytics.

---

# 29. Product Architecture Principle

Vertical customization نباید هسته را fork کند.

ساختار مطلوب:

**Core Engine**
- Typed Work Item / Task
- Parent/Child hierarchy
- Attribute Schema / Custom Fields
- Dynamic forms/layouts
- Team / Roles / Permissions
- Workflow
- Reminder
- Report Query/Definition Engine
- Attachments
- Audit
- AI
- Integrations

+

**Healthcare Vertical Profile**
- Patient typed item
- Patient attribute schema / clinical record
- Session / Visit child item
- Follow-up / Treatment Action child item
- Clinic roles and permissions
- Clinic-specific Web views/reports
- Clinic Telegram flows
- Clinic roles
- Dental templates
- Clinic metrics

+

**Customer Configuration**
- branding
- custom fields
- rules
- notifications
- branch setup

---

# 30. Multi-Tenant Vision

برای SaaS شدن واقعی:

- tenant isolation؛
- clinic configuration؛
- role isolation؛
- branch boundaries؛
- audit؛
- secure integrations؛
- configurable retention.

نباید هر customer نیاز به deployment code متفاوت داشته باشد.

---

# 31. Security & Privacy Product Requirements

حداقل اصول:

- least privilege؛
- RBAC؛
- audit log؛
- secure authentication؛
- encryption in transit؛
- encryption at rest where appropriate؛
- backup؛
- retention policy؛
- controlled exports؛
- secure deletion process؛
- incident logging.

جزئیات در سند security/compliance توسعه می‌یابد.

---

# 32. Integration Philosophy

Integration زمانی ساخته شود که یکی از این شروط را داشته باشد:

1. duplicate data entry را کم کند؛
2. trigger مهم ایجاد کند؛
3. outcome را sync کند؛
4. blocker فروش تکرارشونده باشد.

Integration صرفاً برای logo wall ساخته نشود.

---

# 33. Priority Integrations

ترتیب اولیه:

1. Calendar / appointment data؛
2. clinic PMS via API/export؛
3. SMS/communication؛
4. WhatsApp where applicable؛
5. email؛
6. payments only if workflow needs it.

---

# 34. Automation Vision

Automation engine باید بتواند ruleهایی مانند زیر را اجرا کند:

- وقتی case وارد stage شد → task بساز؛
- اگر task تا X ساعت complete نشد → remind؛
- اگر Y ساعت overdue شد → manager؛
- اگر outcome = no answer → follow-up جدید؛
- اگر treatment complete شد → post-op task؛
- اگر next action خالی شد → flag.

---

# 35. AI + Automation Future

در آینده:

**Event → AI Understanding → Workflow Rule → Human Confirmation → Action**

مثال:

پیام:
«خانم احمدی جواب نداد، سه‌شنبه دوباره زنگ بزن.»

سیستم:
- patient context؛
- outcome = no answer؛
- new follow-up Tuesday؛
- owner same coordinator.

بدون فرم پیچیده.

---

# 36. Product Experience by Role

## Reception
Telegram queue.

## Coordinator
Follow-up workspace.

## Manager
Operations dashboard.

## Doctor
Quick delegation + approvals.

## Owner
Executive overview.

## Admin
Configuration + permissions.

---

# 37. Product Anti-Patterns

نباید:

- همه چیز را customizable کنیم؛
- پزشک را admin کنیم؛
- هر event را notification کنیم؛
- patient data را بدون purpose، permission، retention و audit مشخص ذخیره کنیم؛
- customer-specific fork بسازیم؛
- AI را قبل از workflow تثبیت کنیم؛
- featureهای PMS را یکی‌یکی copy کنیم.

---

# 38. Time-to-Value Target

یک کلینیک باید بتواند:

- در یک session setup اولیه شود؛
- همان روز اولین workflow را اجرا کند؛
- در هفته اول value عملیاتی ببیند.

در Product Roadmap باید target عددی دقیق بعد از Pilot تعیین شود.

---

# 39. Adoption Principle

محصول باید از workflow فعلی وارد شود و سپس آن را بهتر کند.

نه:
«اول همه رفتارهای خود را تغییر دهید، بعد محصول value می‌دهد.»

راه:
- Telegram؛
- import؛
- templates؛
- gradual rollout؛
- 2 workflows first.

---

# 40. Expansion Vision

بعد از Dental PMF:

## Horizontal Expansion داخل Clinic
- HR tasks؛
- marketing؛
- finance approvals؛
- inventory actions.

## Vertical Expansion
- dermatology؛
- beauty؛
- physiotherapy؛
- specialist practices.

## Organization Expansion
- multi-branch؛
- central operations؛
- franchise/network.

---

# 41. Long-term Moat

Moat از task feature ساخته نمی‌شود.

Moat احتمالی:

- vertical workflow library؛
- implementation knowledge؛
- integration depth؛
- operational benchmark data؛
- role-specific UX؛
- AI operational context؛
- switching cost ناشی از process standardization.

---

# 42. Product Decision Framework

هر feature جدید با این سؤال‌ها ارزیابی شود:

1. کدام JTBD را حل می‌کند؟
2. کدام Persona استفاده می‌کند؟
3. frequency چیست؟
4. pain severity چیست؟
5. outcome چیست؟
6. آیا system-of-action را قوی‌تر می‌کند؟
7. آیا integration بهتر از build است؟
8. آیا data/compliance risk دارد؟
9. آیا adoption را ساده می‌کند؟
10. آیا برای یک customer است یا segment؟

---

# 43. Vision Statement نهایی

**TaskMG می‌خواهد زیرساخت اجرای عملیات کلینیک باشد: یک سیستم ساده برای frontline، قابل کنترل برای manager و قابل اندازه‌گیری برای owner که تمام Next Actionهای مهم را از ایجاد تا نتیجه قابل پیگیری می‌کند، در حالی که نرم‌افزارهای تخصصی موجود کلینیک را به‌جای جایگزینی، به هم متصل می‌کند.**
