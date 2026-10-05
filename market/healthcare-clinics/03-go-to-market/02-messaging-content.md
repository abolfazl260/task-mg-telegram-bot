# Messaging و Content — Healthcare Clinics

> وضعیت سند: Messaging System v1  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> Positioning: Clinic Operations & Follow-up Platform  
> اصل: پیام باید از Pain → Mechanism → Outcome → Proof حرکت کند؛ نه از Feature List.

---

# 1. Core Message

**هیچ کار مهمی در کلینیک گم نشود.**

TaskMG پیگیری بیمار و کارهای داخلی را از پیام، تماس و حافظه افراد به Next Actionهای مشخص با Owner، Deadline، Outcome و Visibility مدیریتی تبدیل می‌کند.

---

# 2. Message Architecture

## Problem

کارها بین افراد و ابزارها پخش شده‌اند.

## Consequence

- missed follow-up
- unclear ownership
- delayed handoff
- hidden backlog
- manager status chasing

## Mechanism

TaskMG:
- action را capture می‌کند؛
- owner می‌دهد؛
- due مشخص می‌کند؛
- reminder/escalation می‌دهد؛
- outcome/next action را ثبت می‌کند؛
- dashboard می‌سازد.

## Outcome

- execution قابل اعتمادتر
- cognitive load کمتر
- management visibility بیشتر
- process repeatable

## Proof

- Telegram-first execution
- Web management
- vertical workflows
- measurable pilot

---

# 3. Messaging Rule

پیام عمومی:

**Operations, not Tasks.**

نباید:
«مدیریت تسک قدرتمند برای همه»

باید:
«هر follow-up و handoff کلینیک یک Next Action قابل پیگیری داشته باشد.»

---

# 4. پیام برای مالک کلینیک

## Primary Pain

«نمی‌دانم چه چیزی عقب افتاده تا وقتی مشکل ایجاد شود.»

## Primary Outcome

Visibility بدون micromanagement.

## Message

**ببینید چه کارهایی باز، overdue یا بدون مسئول هستند—بدون اینکه برای status از تک‌تک افراد سؤال کنید.**

## Secondary Value

- کاهش dependency به staff کلیدی
- standardization
- scale readiness
- operational control

## CTA

«Workflow کلینیکتان را ارزیابی کنید.»

---

# 5. پیام برای مدیر کلینیک

## Pain

- چند کانال
- follow-up دستی
- unclear owner
- status chasing

## Message

**یک صف عملیاتی واحد برای تمام کارهای باز کلینیک: چه کاری، برای چه کسی، دست چه فردی و تا چه زمانی.**

## Proof Story

Today / Overdue / Blocked / Escalated / No Next Action.

## CTA

«یک workflow واقعی را در Demo اجرا کنید.»

---

# 6. پیام برای پزشک / دندان‌پزشک

## Pain

- admin interruption
- staff asks for status
- delegation lost
- too much data entry

## Message

**کار را سریع واگذار کنید و فقط زمانی برگردید که تصمیم شما لازم است.**

## Design Promise

- voice/quick delegation
- low interaction
- exception notification

## Avoid

«پزشک باید همه taskها را مدیریت کند.»

---

# 7. پیام برای پذیرش

## Pain

- callbacks
- interruptions
- memory load
- sticky notes/chat

## Message

**هر چیزی که باید بعداً یادت بماند، همان لحظه به یک کار زمان‌دار تبدیل کن.**

## Emotional Benefit

«دیگر لازم نیست همه چیز را در ذهن نگه داری.»

---

# 8. پیام برای Patient Coordinator

## Pain

- no-next-action patients
- duplicate contact
- follow-up spreadsheet
- lost treatment opportunities

## Message

**هر بیمار همیشه یک Next Action مشخص داشته باشد.**

## Core View

- Due Today
- Overdue
- No Answer
- Rescheduled
- Converted/Closed

---

# 9. پیام برای Multi-Branch Operations

## Pain

هر شعبه process متفاوت دارد.

## Message

**یک استاندارد عملیاتی، چند شعبه، یک دید مدیریتی.**

## Value

- central templates
- branch queues
- comparison
- audit

---

# 10. Pain-Based Messaging

## Follow-up Leakage

Headline:
**چند بیمار این هفته باید پیگیری می‌شدند اما هیچ Owner مشخصی نداشتند؟**

Body:
اگر callback در دفتر، chat یا حافظه افراد باشد، manager فقط بعد از تأخیر متوجه می‌شود.

CTA:
Workflow Audit.

---

## Manager Blindness

Headline:
**برای فهمیدن وضعیت کلینیک چند نفر را باید بپرسید؟**

Body:
backlog باید در dashboard دیده شود، نه با status meeting جمع شود.

---

## Staff Dependency

Headline:
**اگر پذیرش کلیدی فردا مرخص باشد، context کارهای باز کجاست؟**

Body:
process باید داخل سیستم باشد، نه فقط در ذهن افراد.

---

## Lab Delay

Headline:
**کار لابراتوار آماده نشده یا فقط کسی پیگیری نکرده؟**

Body:
هر lab case باید expected date، owner و escalation داشته باشد.

---

# 11. Outcome-Based Messaging

به‌جای vague productivity:

### بهتر
«کارهای overdue را قبل از تبدیل‌شدن به شکایت ببینید.»

### بهتر
«هر follow-up با Outcome و Next Action بسته شود.»

### بهتر
«پایان روز backlog واقعی کلینیک را ببینید.»

### بهتر
«workflow بین شیفت‌ها context خود را حفظ کند.»

---

# 12. Mechanism-Based Messaging

Customer باید بفهمد Product چگونه Outcome ایجاد می‌کند.

**Event → Next Action → Owner → Due → Reminder → Outcome → Dashboard**

این chain باید در Demo، Landing Page و Sales Deck ثابت باشد.

---

# 13. Objection-Based Content

## Objection 1 — «نرم‌افزار کلینیک داریم»

Content:
**PMS چه چیزی را ثبت می‌کند و چه چیزی را اجرا نمی‌کند؟**

Message:
TaskMG جایگزین system-of-record نیست؛ execution layer است.

---

## Objection 2 — «تیم استفاده نمی‌کند»

Content:
**چرا workflow باید از رفتار موجود تیم شروع شود؟**

Message:
Telegram-first + 2 workflow pilot + minimal fields.

---

## Objection 3 — «یک نرم‌افزار دیگر نمی‌خواهیم»

Content:
**چه زمانی اضافه‌کردن یک workflow layer بهتر از مهاجرت کامل است؟**

---

## Objection 4 — «می‌توانیم با ClickUp بسازیم»

Content:
**Blank Canvas vs Clinic Workflow**

منصفانه:
اگر تیم already از ClickUp عالی استفاده می‌کند و pain ندارد، migration ضروری نیست.

---

## Objection 5 — «AI و اطلاعات بیمار خطرناک است»

Content:
**Operational AI vs Clinical AI**

توضیح:
- permission-aware
- human-in-the-loop
- minimum data
- no diagnosis

---

# 14. Content Pillars

## Pillar A — Clinic Operations

Topics:
- daily operations
- handoff
- accountability
- manager visibility

## Pillar B — Patient Follow-up

- treatment plan follow-up
- recall
- no-show
- callback

## Pillar C — Workflow Design

- owner
- due
- outcome
- next action
- escalation

## Pillar D — Clinic Growth Operations

- scaling team
- branch expansion
- manager role
- standardization

## Pillar E — AI & Automation

- voice-to-task
- manager brief
- safe automation
- what not to automate

## Pillar F — Product Proof

- demo
- pilot result
- case study
- customer story

---

# 15. Content Formats

## Short-form

- LinkedIn post
- Instagram carousel
- short video
- workflow diagram

## Mid-form

- checklist
- comparison
- case breakdown
- email sequence

## Long-form

- guide
- webinar
- playbook
- case study
- benchmark report

---

# 16. Content Funnel

## Awareness

«5 نشانه اینکه عملیات کلینیک به حافظه افراد وابسته است»

## Consideration

«PMS vs Operations Workflow Platform»

## Intent

«Clinic Workflow Audit»

## Evaluation

«Demo: Treatment Plan Follow-up»

## Decision

«Pilot Plan + Security Overview»

## Expansion

«Multi-branch Operations Playbook»

---

# 17. Landing Page Structure

## Section 1 — Hero

Headline:
**عملیات کلینیک را از پیام و حافظه خارج کنید.**

Subheadline:
هر follow-up و کار داخلی را به Next Action مشخص با مسئول، موعد و وضعیت تبدیل کنید.

CTA:
**درخواست Demo**

Secondary CTA:
**ارزیابی Workflow کلینیک**

---

## Section 2 — Problem

سه ستون:

- Follow-ups get missed
- Ownership is unclear
- Managers lack visibility

---

## Section 3 — How It Works

1. Capture
2. Assign
3. Follow
4. Escalate
5. Report

---

## Section 4 — Key Workflows

- Treatment Follow-up
- Callback
- Lab Case
- Post-Treatment
- Daily Checklist

---

## Section 5 — By Role

Owner / Manager / Reception / Doctor.

---

## Section 6 — Product Surfaces

Telegram:
Execution.

Web:
Control.

---

## Section 7 — Proof

Pilot metrics / customer quote / case study.

---

## Section 8 — Integration Positioning

«نرم‌افزار فعلی را نگه دارید.»

---

## Section 9 — Trust

- role-based access
- audit
- data boundaries
- support

تا قبل از certification رسمی، عبارت‌های compliance-certified استفاده نشود.

---

## Section 10 — CTA

Demo / Workflow Audit.

---

# 18. Demo Narrative

Demo باید story باشد.

## Scenario

بیمار consultation شده و می‌گوید هفته بعد تماس بگیرید.

### Old Way

Reception یادداشت می‌کند / chat.

### TaskMG

1. Follow-up ساخته می‌شود.
2. Coordinator owner.
3. Due Tuesday.
4. Tuesday queue.
5. No Answer outcome.
6. Auto/quick reschedule.
7. Manager sees overdue.
8. Final outcome.

Demo باید dashboard را به workflow وصل کند.

---

# 19. Demo Rule

Generic feature tour ندهیم.

بد:
«این Tags است، این Comments است...»

خوب:
«یک بیمار consultation شده؛ حالا ببینیم تا next action چه می‌شود.»

---

# 20. Case Study Structure

## 1. Customer

- clinic type
- size
- workflow

## 2. Before

- current process
- pain
- baseline

## 3. Implementation

- workflows chosen
- users
- duration

## 4. Results

فقط measured:

- follow-up completion
- overdue
- manager time
- adoption

## 5. Quote

Specific outcome.

## 6. Lessons

چه چیزی تغییر کرد؟

---

# 21. Case Study Guardrail

نباید:

- patient-identifying information
- exaggerated revenue attribution
- causal claim بدون data
- clinical result claim

---

# 22. Sales Deck Messaging

Recommended flow:

1. Why operations break
2. Cost of fragmented action
3. System of Record vs Action
4. Product workflow
5. Role value
6. Demo workflow
7. Pilot
8. Security
9. Pricing
10. Next Step

---

# 23. Email Nurture Themes

## Email 1
Problem:
Follow-up leakage.

## Email 2
Framework:
Owner + Due + Outcome + Next Action.

## Email 3
Example:
Lab workflow.

## Email 4
Manager:
Visibility.

## Email 5
CTA:
Workflow Audit.

---

# 24. Social Content Series

## Series 1 — Clinic Workflow Mistakes

10 short posts.

## Series 2 — Before / After Process

visual workflow.

## Series 3 — Manager Metrics

overdue / no-next-action / cycle time.

## Series 4 — AI Without Hype

operational automation examples.

---

# 25. SEO Content Map

## Pillar

Clinic Operations Software

## Cluster

- dental follow-up system
- clinic workflow management
- dental lab tracking
- dental office checklist
- dental team task management
- patient recall workflow
- no-show follow-up

---

# 26. Competitive Content

Comparison pages باید fair و use-case-based باشند:

- TaskMG vs General Task Manager
- TaskMG + PMS vs PMS alone
- TaskMG vs Spreadsheet
- Structured Workflow vs Messaging Group

نباید unsupported competitor claims نوشته شود.

---

# 27. Localization

برای هر market:

- terminology
- messaging channel
- legal wording
- pricing currency
- examples
- working hours

localized شود.

Translation به‌تنهایی localization نیست.

---

# 28. Voice & Tone

برای Buyer:

- concrete
- operational
- low-hype
- proof-driven

از jargon AI بی‌دلیل پرهیز.

---

# 29. CTA Hierarchy

## Primary

Book Demo

## Secondary

Workflow Audit

## Tertiary

Download Checklist / Watch Demo

یک page نباید 5 CTA هم‌ارزش داشته باشد.

---

# 30. Messaging Validation

در Discovery بپرسیم:

- کدام عبارت بیشترین relevance داشت؟
- «Operations» قابل فهم است؟
- Follow-up یا Workflow کدام term بهتر است؟
- آیا فکر کردید product قرار است PMS را جایگزین کند؟
- کدام outcome ارزشمندتر است؟

---

# 31. Content Metrics

## Awareness Content

- ICP engagement
- qualified reach

## Educational

- completion/read
- return visitor
- audit CTA

## Conversion

- demo booking
- qualified rate
- pipeline

## Proof

- influenced opportunities
- sales usage

---

# 32. Content Production Rule

هر Content باید یک row در matrix داشته باشد:

- Persona
- Journey Stage
- Pain
- Message
- CTA
- Metric

اگر هیچ‌کدام مشخص نیست، content احتمالاً noise است.

---

# 33. Messaging Library — Short Lines

- هیچ follow-up بدون Next Action.
- هر کار یک Owner.
- backlog را ببینید، نه اینکه حدس بزنید.
- Telegram برای اجرا؛ Web برای مدیریت.
- از پیام تا انجام.
- نرم‌افزار کلینیک را عوض نکنید؛ execution را منظم کنید.
- هر Case فعال، یک اقدام بعدی مشخص.

---

# 34. Final Messaging System

ترتیب استاندارد همه assetها:

**Pain → Workflow Gap → TaskMG Mechanism → Operational Outcome → Proof → CTA**

و نه:

**Feature → Feature → AI → Feature → CTA**
