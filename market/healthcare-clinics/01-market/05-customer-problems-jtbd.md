# مشکلات مشتری و Jobs To Be Done

> وضعیت سند: Business v1  
> بازار مرجع: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> هدف: تبدیل Painهای مشاهده‌شده به Jobهای قابل طراحی، قابل فروش و قابل اندازه‌گیری.

---

## 1. خلاصه مدیریتی

مسئله اصلی بازار این نیست که کلینیک «Task Manager» ندارد. مسئله این است که بخش مهمی از عملیات بین افراد، پیام‌ها، تماس‌ها، حافظه کارکنان و نرم‌افزارهای مختلف پخش شده و برای بسیاری از اقدامات، **Next Action، Owner، Deadline و Visibility مدیریتی** به‌صورت استاندارد وجود ندارد.

بنابراین Job اصلی محصول این است:

**وقتی یک رویداد در مسیر بیمار یا عملیات کلینیک نیازمند اقدام می‌شود، آن اقدام باید در لحظه به کار قابل‌ردیابی با مسئول، موعد، context، reminder و status تبدیل شود و تا بسته‌شدن از دید تیم و مدیر خارج نشود.**

این سند Painها را از چهار زاویه تحلیل می‌کند:

1. Functional Jobs — کاری که باید انجام شود؛
2. Emotional Jobs — احساسی که کاربر می‌خواهد تجربه کند یا از آن دوری کند؛
3. Social Jobs — تصویری که کاربر می‌خواهد نزد دیگران داشته باشد؛
4. Business Outcomes — نتیجه‌ای که Buyer بابت آن پول می‌دهد.

---

# 2. Problem Tree

## 2.1 Problem Statement اصلی

در کلینیک، «کار بعدی» اغلب وجود دارد اما ساختار ندارد.

نمونه:

- بیمار consultation شده؛
- پزشک treatment plan داده؛
- پذیرش باید تماس بگیرد؛
- بیمار باید تصمیم بگیرد؛
- لابراتوار باید چیزی آماده کند؛
- دستیار باید نتیجه را پیگیری کند؛
- بیمار باید برای جلسه بعدی برگردد.

اگر این زنجیره به task/workflow تبدیل نشود، وضعیت به یکی از این شکل‌ها باقی می‌ماند:

- در حافظه یک فرد؛
- داخل چت؛
- روی کاغذ؛
- در دفتر؛
- در Excel؛
- در note نرم‌افزار کلینیک؛
- یا اصلاً ثبت نمی‌شود.

## 2.2 Root Causes

### Process
- workflow تعریف نشده؛
- handoff استاندارد نیست؛
- checklist وجود ندارد؛
- escalation تعریف نشده.

### People
- نقش‌ها overlap دارند؛
- مسئولیت شفاهی است؛
- افراد در شیفت‌های مختلف هستند؛
- turnover باعث از دست رفتن context می‌شود.

### Tools
- سیستم فعلی record-centric است نه action-centric؛
- پیام‌رسان ساختار task ندارد؛
- Excel real-time نیست؛
- ابزار task عمومی context بیمار را نمی‌شناسد.

### Management
- dashboard عملیاتی وجود ندارد؛
- backlog قابل اندازه‌گیری نیست؛
- manager دیر متوجه bottleneck می‌شود؛
- performance با anecdote سنجیده می‌شود.

---

# 3. Pain Map بر اساس نقش

## 3.1 مالک / Owner

### Painهای اصلی
- نمی‌داند چه تعداد follow-up عقب افتاده است؛
- نمی‌داند کدام بیمار یا opportunity در حال از دست رفتن است؛
- به افراد کلیدی وابسته است؛
- برای status باید از manager سؤال کند؛
- رشد مجموعه باعث chaos می‌شود.

### Impact
- revenue leakage؛
- کاهش اعتماد به تیم؛
- micromanagement؛
- ضعف scalability.

### Severity
**5/5**

---

## 3.2 مدیر کلینیک

### Painهای اصلی
- taskهای زیادی از کانال‌های مختلف وارد می‌شوند؛
- owner همیشه مشخص نیست؛
- کارها به او escalate می‌شوند وقتی دیر شده؛
- پایان روز نمی‌تواند backlog واقعی را ببیند؛
- بین شیفت‌ها اطلاعات از دست می‌رود.

### Impact
- context switching؛
- stress؛
- status chasing؛
- overtime؛
- blame.

### Severity
**5/5**

---

## 3.3 پذیرش

### Painهای اصلی
- interruption زیاد؛
- تماس‌های callback؛
- هم‌زمانی بیمار حضوری و تلفن؛
- reminder ذهنی؛
- درخواست شفاهی پزشک؛
- «بعداً زنگ بزن»های زیاد.

### Impact
- فراموشی؛
- اشتباه؛
- فشار ذهنی؛
- تجربه ضعیف بیمار.

### Severity
**5/5**

---

## 3.4 Patient Coordinator / Follow-up

### Painهای اصلی
- لیست callback شفاف نیست؛
- next action مشخص نیست؛
- outcome تماس‌ها استاندارد ثبت نمی‌شود؛
- چند نفر ممکن است به یک بیمار تماس بزنند؛
- بیمار treatment plan دارد ولی pipeline مشخص نیست.

### Impact
- فرصت فروش درمان از دست می‌رود؛
- duplicate work؛
- گزارش conversion ناقص.

### Severity
**5/5**

---

## 3.5 پزشک / دندان‌پزشک

### Painهای اصلی
- staff برای status سؤال می‌پرسد؛
- کارهای اداری interrupt می‌کنند؛
- درخواست‌های داده‌شده قابل پیگیری نیستند؛
- بعضی prerequisiteها قبل از ویزیت آماده نیستند.

### Impact
- زمان بالینی هدر می‌رود؛
- frustration؛
- تصمیم‌گیری دیرتر.

### Severity
**3.5/5**

---

## 3.6 دستیار

### Painهای اصلی
- checklist شفاهی؛
- تغییر اولویت؛
- آماده‌سازی ناقص؛
- dependency به پزشک یا پذیرش؛
- handoff بین شیفت.

### Impact
- دوباره‌کاری؛
- تأخیر؛
- خطای عملیاتی.

### Severity
**4/5**

---

# 4. Problem Categories

## P1 — Follow-up Leakage

### تعریف
اقدامی که باید بعد از یک رویداد انجام شود، انجام نمی‌شود یا دیر انجام می‌شود.

### مثال
- تماس بعد از consultation؛
- تماس بعد از missed appointment؛
- پیگیری درمان شروع‌نشده؛
- post-op call؛
- recall.

### Root Cause
- no owner؛
- no due date؛
- manual list؛
- interruption.

### Business Impact
- lost treatment opportunity؛
- patient dissatisfaction؛
- lower reactivation.

### Priority
**Critical**

---

## P2 — Unclear Ownership

### تعریف
کار مشخص است ولی «چه کسی مسئول نهایی است؟» واضح نیست.

### نشانه‌ها
- «فکر کردم فلانی انجام می‌دهد»؛
- چند نفر می‌بینند ولی کسی انجام نمی‌دهد؛
- manager مجبور به follow-up دستی است.

### Business Impact
- accountability پایین؛
- blame؛
- delay.

### Priority
**Critical**

---

## P3 — No Next Action

### تعریف
برای بیمار یا case وضعیت داریم ولی اقدام بعدی تعریف نشده.

### مثال
Patient status = "Treatment Plan Sent" اما هیچ callback date وجود ندارد.

### Business Impact
- pipeline stagnation؛
- missed revenue؛
- lost context.

### Priority
**Critical**

---

## P4 — Fragmented Communication

### تعریف
context در چت، تماس، سیستم، note و حافظه افراد پخش شده است.

### نتیجه
- duplicate question؛
- incomplete handoff؛
- context loss.

### Priority
**High**

---

## P5 — Treatment Workflow Fragmentation

### تعریف
درمان چندمرحله‌ای به‌صورت case workflow مدیریت نمی‌شود.

### Use Cases
- ایمپلنت؛
- پروتز؛
- ارتودنسی؛
- lab cases؛
- multi-appointment plans.

### Business Impact
- delay؛
- incomplete prerequisites؛
- poor patient experience.

### Priority
**High**

---

## P6 — Manager Blindness

### تعریف
مدیر نمی‌تواند بدون پرسیدن از افراد وضعیت عملیات را ببیند.

### نشانه
- daily report دستی؛
- status meeting برای جمع‌کردن اطلاعات؛
- backlog نامعلوم.

### Priority
**Critical برای Buyer**

---

## P7 — Staff Dependency

### تعریف
بخشی از عملیات فقط با دانش یک فرد کار می‌کند.

### Trigger
مرخصی، استعفا یا تغییر شیفت باعث disruption می‌شود.

### Priority
**High**

---

## P8 — Weak Escalation

### تعریف
task overdue می‌شود اما کسی جز owner مطلع نمی‌شود.

### Business Impact
مشکل فقط وقتی بیمار شکایت می‌کند یا manager متوجه می‌شود دیده می‌شود.

### Priority
**High**

---

## P9 — Poor Shift Handoff

### تعریف
کارهای باز بین شیفت یا روز بعد منتقل نمی‌شوند.

### Priority
**Medium to High**

---

## P10 — No Operational Analytics

### تعریف
داده کافی برای فهم bottleneck وجود ندارد.

### سؤال‌هایی که بدون سیستم جواب ندارند
- چند follow-up overdue داریم؟
- متوسط زمان بستن callback چقدر است؟
- کدام workflow بیشتر گیر می‌کند؟
- کدام نوع task بیشترین delay دارد؟

### Priority
**High برای Management، پایین‌تر برای frontline**

---

# 5. Jobs To Be Done

## 5.1 Core Job

### Situation
وقتی در کلینیک اتفاقی رخ می‌دهد که نیازمند اقدام بعدی است...

### Motivation
می‌خواهم اقدام مشخص، مسئول، زمان و context داشته باشد...

### Expected Outcome
تا مطمئن شوم هیچ کار مهمی گم نمی‌شود و مدیر بدون پرس‌وجوی دستی وضعیت را می‌بیند.

---

# 6. Functional Jobs

## FJ1 — Capture the Next Action

**وقتی یک بیمار، تماس، پیام یا تصمیم درمانی نیازمند اقدام بعدی است، می‌خواهم آن را در چند ثانیه ثبت کنم تا بعداً فراموش نشود.**

### Requirements
- fast capture؛
- Telegram؛
- voice؛
- template؛
- default fields.

### Metric
Time-to-create-task.

---

## FJ2 — Assign Clear Ownership

**می‌خواهم هر کار یک owner مشخص داشته باشد تا مسئولیت مبهم نباشد.**

### Metric
Unassigned task rate.

---

## FJ3 — Make Time Explicit

**می‌خواهم زمان انجام یا follow-up مشخص باشد تا کار فقط در یک لیست باقی نماند.**

### Metric
Tasks without due date.

---

## FJ4 — See Today's Work

**می‌خواهم هر فرد بداند امروز چه کارهایی دارد و کدام‌ها urgent هستند.**

### Metric
Daily task completion.

---

## FJ5 — Handoff Work Safely

**وقتی شیفت یا مسئول تغییر می‌کند، می‌خواهم context همراه کار منتقل شود.**

### Metric
Reopened / clarification rate.

---

## FJ6 — Track Treatment-related Operational Steps

**برای درمان‌های چندمرحله‌ای می‌خواهم مرحله‌های غیرکلینیکی و coordination قابل‌ردیابی باشند.**

### Metric
Workflow stage delay.

---

## FJ7 — Manage Follow-up Queue

**می‌خواهم بیمارانی که نیاز به تماس دارند بر اساس موعد و اولویت در یک queue باشند.**

### Metric
Median follow-up delay.

---

## FJ8 — Escalate Exceptions

**اگر کاری انجام نشد می‌خواهم قبل از تبدیل شدن به شکایت یا مشکل به manager اطلاع داده شود.**

### Metric
Overdue-to-escalation time.

---

## FJ9 — Standardize Repeatable Work

**می‌خواهم کارهای تکراری با template یکسان اجرا شوند.**

### Metric
Template adoption rate.

---

## FJ10 — Review Operational Health

**می‌خواهم dashboard نشان دهد backlog، overdue و bottleneck کجاست.**

### Metric
Manager reporting time.

---

# 7. Emotional Jobs

## EJ1 — کاهش ترس از فراموشی
پذیرش می‌خواهد مطمئن باشد چیزی از قلم نمی‌افتد.

## EJ2 — کاهش حس chaos
مدیر می‌خواهد احساس کند عملیات تحت کنترل است.

## EJ3 — کاهش blame
کاربر می‌خواهد مشخص باشد چه کاری به او سپرده شده و چه زمانی انجام داده است.

## EJ4 — اعتماد به تیم
مالک می‌خواهد بدون دخالت دائمی مطمئن باشد فرآیند کار می‌کند.

## EJ5 — کاهش cognitive load
کاربر frontline نمی‌خواهد همه چیز را در ذهن نگه دارد.

---

# 8. Social Jobs

## SJ1 — حرفه‌ای دیده شدن نزد بیمار
پیگیری به‌موقع باعث می‌شود کلینیک منظم به نظر برسد.

## SJ2 — مدیر قابل اعتماد بودن
manager می‌خواهد به مالک نشان دهد عملیات کنترل‌شده است.

## SJ3 — تیم هماهنگ
کارکنان می‌خواهند در مقابل همکاران مسئولیت‌پذیر دیده شوند.

## SJ4 — مالک سیستم‌محور
مالک می‌خواهد کسب‌وکار وابسته به افراد نباشد.

---

# 9. Outcome Statements

Outcomeها باید مستقل از feature نوشته شوند.

## O1
کاهش احتمال فراموش شدن follow-up.

## O2
کاهش زمان بین event و first action.

## O3
کاهش تعداد کارهای بدون owner.

## O4
کاهش تعداد کارهای overdue.

## O5
کاهش زمان manager برای جمع‌آوری status.

## O6
افزایش درصد caseهایی که Next Action دارند.

## O7
کاهش duplicate communication.

## O8
کاهش dependency به افراد کلیدی.

## O9
افزایش consistency بین شیفت‌ها و شعب.

## O10
افزایش visibility روی bottleneck.

---

# 10. Outcome Metrics پیشنهادی

| Outcome | Metric |
|---|---|
| Follow-up انجام شود | Follow-up completion rate |
| سریع انجام شود | Median time-to-follow-up |
| کار صاحب داشته باشد | % tasks with owner |
| کار زمان داشته باشد | % tasks with due date |
| backlog کنترل شود | Open tasks / overdue tasks |
| manager visibility | Time to prepare daily report |
| handoff بهتر شود | Clarification/reassignment rate |
| workflow پایدار باشد | Stage cycle time |
| next action گم نشود | Cases without next action |
| adoption | Weekly active operational users |

---

# 11. Pain Priority Matrix

| Pain | Frequency | Severity | Economic Impact | Product Fit | Priority |
|---|---:|---:|---:|---:|---|
| Follow-up leakage | 5 | 5 | 5 | 5 | P0 |
| Unclear ownership | 5 | 5 | 4 | 5 | P0 |
| No next action | 5 | 5 | 5 | 5 | P0 |
| Manager blindness | 4 | 5 | 4 | 5 | P0 |
| Fragmented communication | 5 | 4 | 3 | 5 | P1 |
| Treatment workflow fragmentation | 4 | 5 | 4 | 4 | P1 |
| Weak escalation | 4 | 4 | 4 | 5 | P1 |
| Staff dependency | 4 | 4 | 4 | 4 | P1 |
| Poor shift handoff | 3 | 4 | 3 | 4 | P2 |
| No analytics | 3 | 4 | 3 | 5 | P2 |

این امتیازها فرضیه اولیه‌اند و باید با interview و Pilot اصلاح شوند.

---

# 12. Problem → Feature Mapping

| Problem | Capability |
|---|---|
| Follow-up leakage | Reminder + queue + due date |
| Unclear ownership | Assignee + role |
| No next action | Required next-action state |
| Fragmented communication | Task comments + patient/case context |
| Treatment fragmentation | Workflow template |
| Manager blindness | Dashboard + filters |
| Weak escalation | Overdue alert + escalation rule |
| Staff dependency | Shared history + audit |
| Shift handoff | Open-task handover view |
| No analytics | Reports + cycle time metrics |

---

# 13. Non-Problems / Scope Discipline

TaskMG نباید هر درد کلینیک را حل کند.

در MVP، این مسائل خارج از Core Job هستند:

- تشخیص پزشکی؛
- نسخه‌نویسی؛
- clinical charting جامع؛
- imaging/PACS؛
- claim processing بیمه؛
- accounting کامل؛
- payroll؛
- inventory ERP کامل.

اگر مشتری این مسائل را Pain اصلی معرفی کند، احتمالاً Lead برای محصول فعلی مناسب نیست یا integration لازم دارد.

---

# 14. Interview Guide برای JTBD Validation

## Timeline Questions
- آخرین بار که یک follow-up فراموش شد چه اتفاقی افتاد؟
- از لحظه ایجاد نیاز تا انجام کار چه کسانی درگیر بودند؟
- کار ابتدا کجا ثبت شد؟
- چه زمانی فهمیدید انجام نشده؟

## Switching Questions
- الان برای مدیریت این موضوع از چه چیزی استفاده می‌کنید؟
- چه چیزی در روش فعلی آزاردهنده است؟
- آیا ابزار دیگری امتحان کرده‌اید؟
- چرا ادامه ندادید؟

## Outcome Questions
- اگر این مشکل حل شود چه چیزی تغییر می‌کند؟
- کدام metric برای شما مهم است؟
- چه نتیجه‌ای باعث می‌شود بابت این سیستم پول بدهید؟

## Priority Questions
- از بین missed follow-up، no-show، lab delay، task chaos و reporting کدام دردناک‌تر است؟
- هفته گذشته چند بار رخ داد؟
- چه کسی بیشترین آسیب را می‌بیند؟

---

# 15. فرضیه‌های قابل تست

### H1
کلینیک چندپزشکه حداقل چند بار در روز Next Actionهایی دارد که خارج از PMS اصلی مدیریت می‌شوند.

### H2
Front desk برای capture سریع Telegram را به dashboard سنگین ترجیح می‌دهد.

### H3
Owner برای visibility روی overdue حاضر به پرداخت است، حتی اگر frontline featureها را استفاده کنند.

### H4
Follow-up queue یکی از workflowهای با بیشترین perceived value است.

### H5
اگر پزشک مجبور به data entry زیاد شود adoption افت می‌کند.

### H6
Pilot با 2 workflow بهتر از rollout کامل نتیجه می‌دهد.

---

# 16. Definition of Problem-Solution Fit

می‌توان گفت Problem-Solution Fit اولیه داریم اگر در چند Pilot مستقل:

- کاربران بدون فشار مداوم task ثبت کنند؛
- workflow در کار واقعی استفاده شود؛
- manager dashboard را برای تصمیم واقعی باز کند؛
- overdue/follow-up visibility بهتر شود؛
- حداقل یک Buyer حاضر به پرداخت recurring fee باشد؛
- value فقط به «یادآوری» محدود نباشد.

---

# 17. تصمیم محصولی حاصل از JTBD

اولویت MVP باید حول این Loop باشد:

**Capture → Assign → Due → Context → Reminder → Complete → Escalate → Report**

و نه حول ساخت یک پرونده پزشکی جامع.
