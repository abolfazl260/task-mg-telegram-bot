# پرسوناهای Healthcare Clinics

> این سند بین Buyer Persona و User Persona تفکیک می‌کند. هدف، طراحی محصول و پیام فروش برای افراد واقعی در workflow است.

## 1. نقشه نقش‌ها

| Persona | نقش در خرید | نقش در استفاده | قدرت تصمیم |
|---|---|---|---:|
| مالک / دندان‌پزشک مالک | Economic Buyer | متوسط | بسیار بالا |
| مدیر کلینیک | Champion / Buyer | زیاد | بالا |
| سرپرست پذیرش | Influencer | بسیار زیاد | متوسط |
| پذیرش / منشی | User | بسیار زیاد | پایین |
| Coordinator / Follow-up | Champion/User | بسیار زیاد | متوسط |
| دندان‌پزشک / پزشک | Clinical Influencer | کم تا متوسط | متوسط تا بالا |
| دستیار | User | متوسط | پایین |
| مدیر چند شعبه | Buyer/Champion | زیاد | بالا |
| بیمار | Non-user stakeholder | غیرمستقیم | پایین |

---

# 2. Persona A — مالک کلینیک / دندان‌پزشک مالک

## Profile

مالک هم‌زمان مسئول درآمد، کیفیت خدمت، نیروی انسانی و تصمیم‌های کلینیک است. معمولاً زمان محدودی برای مدیریت جزئیات دارد و بسیاری از مشکلات فقط وقتی escalate می‌شوند به او می‌رسند.

## Goals

- افزایش درآمد از ظرفیت موجود؛
- جلوگیری از از دست رفتن بیمار؛
- کنترل عملکرد تیم بدون micromanagement؛
- کاهش وابستگی به کارکنان کلیدی؛
- توسعه کلینیک بدون ایجاد آشفتگی؛
- حفظ تجربه بیمار.

## Pains

- «نمی‌دانم چه کارهایی عقب افتاده.»
- «اگر مدیر/پذیرش نباشد، همه‌چیز به هم می‌ریزد.»
- «بیمار consultation گرفته اما کسی پیگیری نکرده.»
- «برای فهمیدن status باید از چند نفر سؤال کنم.»
- «گروه تلگرام/واتساپ پر از پیام است ولی actionable نیست.»

## Buying Triggers

- شکایت بیمار؛
- کاهش conversion؛
- اضافه شدن پزشک؛
- شعبه جدید؛
- ترک کارمند کلیدی؛
- رشد تبلیغات؛
- افزایش chaos.

## Objections

- «یک نرم‌افزار دیگر نمی‌خواهم.»
- «تیم استفاده نمی‌کند.»
- «همین نرم‌افزار مطب کافی است.»
- «نمی‌خواهم کار پزشک پیچیده شود.»
- «اطلاعات بیمار امن است؟»

## Message

**بدون تغییر نرم‌افزار اصلی کلینیک، کارهای follow-up و عملیات تیم را صاحب‌دار، زمان‌دار و قابل گزارش کنید.**

## Features مهم

- management dashboard؛
- overdue view؛
- team performance؛
- workflow templates؛
- audit/activity log؛
- branch reporting؛
- escalation.

## Success Criteria

- کمتر status chasing؛
- backlog قابل مشاهده؛
- follow-up کمتر از دست برود؛
- تیم مستقل‌تر کار کند؛
- گزارش هفتگی معنی‌دار داشته باشد.

---

# 3. Persona B — مدیر داخلی کلینیک

## Profile

مهم‌ترین Champion احتمالی. بین مالک، پزشکان، پذیرش و تیم اجرایی قرار دارد. بیشترین ارزش روزمره محصول باید برای او ایجاد شود.

## Goals

- هیچ کار مهمی فراموش نشود؛
- owner هر کار روشن باشد؛
- کارهای امروز/عقب‌افتاده را ببیند؛
- بتواند workload را توزیع کند؛
- مشکل را قبل از رسیدن به مالک حل کند.

## Pains

- follow-up دستی؛
- گزارش‌گیری با پرسیدن از افراد؛
- taskهای شفاهی؛
- نبود escalation؛
- اختلاف در این‌که «چه کسی مسئول بود»؛
- عدم visibility در چند شیفت.

## Daily Jobs

- assign؛
- reassign؛
- check overdue؛
- resolve blockers؛
- review missed patient actions؛
- prepare owner report؛
- coordinate schedule exceptions.

## Objections

- «setup خیلی زمان می‌برد.»
- «کاربرها وارد نمی‌کنند.»
- «اگر مجبور باشم دو سیستم را update کنم بدتر می‌شود.»

## Design Implication

محصول باید برای manager:

- bulk actions؛
- quick filters؛
- dashboard؛
- recurring templates؛
- escalation؛
- mobile-friendly flow

داشته باشد.

## Message

**یک صف عملیاتی واحد برای کل کلینیک: چه کاری، برای چه کسی، دست چه فردی و تا چه زمانی.**

---

# 4. Persona C — سرپرست پذیرش / Front Desk Lead

## Profile

در بسیاری از کلینیک‌ها مرکز واقعی coordination است. تماس‌ها، پیام‌ها، نوبت‌ها، شکایت‌ها و درخواست پزشکان از این نقطه عبور می‌کنند.

## Goals

- فراموش نکردن تماس‌ها؛
- پاسخ سریع؛
- کاهش حافظه ذهنی؛
- تحویل درست کار به شیفت بعد؛
- کم کردن تماس‌های تکراری داخلی.

## Pains

- چند کانال هم‌زمان؛
- interruption زیاد؛
- کارهای «بعداً انجام بده»؛
- sticky note و دفتر؛
- chatهای زیاد؛
- بیمارانی که باید دوباره تماس گرفته شوند.

## Biggest Fear

محصول به‌جای کمک، یک لایه data-entry جدید باشد.

## Product Requirements

- ثبت task در کمتر از چند ثانیه؛
- voice/natural language؛
- reminder واضح؛
- simple status؛
- saved filters؛
- handoff بین شیفت؛
- minimal mandatory fields.

## Message

**هر چیزی که باید بعداً یادت بماند، همان لحظه به کار زمان‌دار تبدیل کن.**

---

# 5. Persona D — پذیرش / منشی

## Profile

کاربر پرتکرار و حساس به friction. موفقیت adoption تا حد زیادی به تجربه این Persona وابسته است.

## Goals

- انجام سریع کار؛
- کم شدن فشار ذهنی؛
- پاسخ به بیمار؛
- avoid blame؛
- پایان شیفت با backlog مشخص.

## Pains

- کارهای ناگهانی؛
- تماس‌های هم‌زمان؛
- فراموشی؛
- تغییر اولویت؛
- انتقال شفاهی؛
- درخواست‌های پزشکان.

## Objections

- «وقت ندارم همه چیز را ثبت کنم.»
- «Telegram خودمان را داریم.»
- «باز هم مدیر می‌خواهد کنترل کند.»

## Adoption Strategy

- Telegram-first؛
- create task from message؛
- voice capture؛
- one-tap complete؛
- default templates؛
- notification hygiene؛
- عدم نمایش KPI تنبیهی در onboarding اولیه.

## Success

کاربر بگوید: «دیگر لازم نیست همه چیز را توی ذهنم نگه دارم.»

---

# 6. Persona E — Patient Coordinator / مسئول Follow-up

## Profile

در کلینیک‌های حرفه‌ای‌تر مسئول تبدیل inquiry/consultation به treatment و پیگیری بیمار است.

## Goals

- هیچ lead یا treatment plan از pipeline خارج نشود؛
- next action مشخص باشد؛
- تماس‌ها زمان‌بندی شوند؛
- نتیجه تماس ثبت شود؛
- patient queue اولویت‌بندی شود.

## Pains

- Excel پراکنده؛
- duplicate contact؛
- نبود next action؛
- فراموشی callback؛
- عدم visibility conversion.

## Key Features

- follow-up queue؛
- due date؛
- tags؛
- outcome؛
- templates؛
- reminders؛
- patient context؛
- dashboard.

## Message

**هر بیمار همیشه یک Next Action مشخص داشته باشد.**

## Success Metrics

- follow-up completion rate؛
- delay to first follow-up؛
- treatment acceptance pipeline؛
- no-next-action count.

---

# 7. Persona F — دندان‌پزشک / پزشک

## Profile

زمان بالینی ارزش بالایی دارد. معمولاً نمی‌خواهد وارد workflow اداری پیچیده شود، اما context و outcome برایش مهم است.

## Goals

- کمترین interruption؛
- درخواست کار ساده؛
- اعتماد به اینکه staff پیگیری می‌کند؛
- دیدن موارد مهم و استثناها؛
- حفظ judgment بالینی.

## Pains

- سؤال‌های تکراری staff؛
- patient context ناقص؛
- missed preparation؛
- آماده نبودن lab/result؛
- کارهای اداری زیاد.

## Objections

- «نمی‌خواهم task management کار کنم.»
- «وقت ندارم فرم پر کنم.»
- «AI نباید وارد تصمیم درمانی شود.»

## Product Design

برای پزشک:

- quick assign؛
- voice instruction؛
- mention/approval؛
- exception notification؛
- minimum interaction.

نباید او را مجبور کرد همه taskها را مدیریت کند.

## Message

**کار را در چند ثانیه واگذار کنید و فقط زمانی برگردید که نیاز به تصمیم شما باشد.**

---

# 8. Persona G — دستیار دندان‌پزشک / Medical Assistant

## Goals

- آماده بودن اتاق/مواد؛
- هماهنگی با پزشک؛
- پیگیری موارد بعد از درمان؛
- اطلاع از کارهای شیفت.

## Pains

- درخواست شفاهی؛
- تغییر اولویت؛
- وابستگی به حضور یک نفر؛
- نبود checklist.

## Features

- checklist؛
- assigned tasks؛
- recurring tasks؛
- attachment؛
- quick completion؛
- shift view.

## Message

**کارهای هر شیفت و هر بیمار واضح و قابل تحویل باشند.**

---

# 9. Persona H — مدیر چند شعبه / Operations Manager

## Profile

این Persona در فاز Scale اهمیت پیدا می‌کند.

## Goals

- استانداردسازی شعب؛
- مقایسه performance؛
- کنترل SLA؛
- کاهش وابستگی به مدیر هر شعبه؛
- rollout یک process مشترک.

## Pains

- هر شعبه روش خودش را دارد؛
- گزارش‌ها قابل مقایسه نیست؛
- owner دید centralized ندارد؛
- escalation دیر انجام می‌شود.

## Needs

- branch hierarchy؛
- permission؛
- central templates؛
- cross-branch reporting؛
- audit؛
- export/API؛
- admin control.

## Message

**یک استاندارد عملیاتی، چند شعبه، یک دید مدیریتی.**

---

# 10. Persona I — بیمار به‌عنوان ذی‌نفع غیرمستقیم

## نکته

در MVP بیمار لزوماً User محصول نیست، اما تجربه او outcome اصلی است.

## Expectations

- تماس به‌موقع؛
- reminder واضح؛
- عدم نیاز به تکرار اطلاعات؛
- follow-up بعد از درمان؛
- پاسخ‌گویی منظم؛
- اطلاع از next step.

## Risks

- پیام زیاد؛
- نقض privacy؛
- ارتباط غیرشخصی؛
- reminder نامناسب؛
- اطلاعات حساس در کانال نادرست.

## Design Rule

هر automation بیمارمحور باید:

- consent-aware؛
- قابل opt-out؛
- حداقلی؛
- context-appropriate؛
- قابل audit

باشد.

---

# 11. Buyer Persona vs User Persona

## Buyer Persona

### Primary
- مالک؛
- مدیر کلینیک.

### Secondary
- مدیر چندشعبه.

Buyer به این موارد اهمیت می‌دهد:

- ROI؛
- visibility؛
- adoption؛
- security؛
- implementation risk؛
- reporting؛
- price.

## User Persona

### Primary
- پذیرش؛
- coordinator؛
- manager.

### Secondary
- assistant؛
- doctor.

User به این موارد اهمیت می‌دهد:

- سرعت؛
- سادگی؛
- notification quality؛
- کم بودن data entry؛
- mobile UX؛
- reliability.

---

# 12. Influencer و Decision Maker Map

| نقش | اثر بر خرید | احتمال مقاومت | راهبرد |
|---|---:|---:|---|
| مالک | بسیار بالا | متوسط | ROI + visibility |
| مدیر | بالا | پایین | workflow demo |
| پذیرش | متوسط | بالا اگر UX بد باشد | co-design + low friction |
| پزشک | بالا | متوسط | حداقل interaction |
| IT | متوسط | متوسط | security/API |
| مالی | متوسط | متوسط | TCO/ROI |
| دستیار | پایین | متوسط | simple checklist |

---

# 13. Persona-specific Demo

### Demo برای مالک
Dashboard → overdue → workload → report → ROI story.

### Demo برای مدیر
Create workflow → assign → escalate → filter → daily view.

### Demo برای پذیرش
Telegram → task in seconds → reminder → complete.

### Demo برای Coordinator
Patient follow-up queue → next action → outcome.

### Demo برای پزشک
Voice assign → approval → exception notification.

### Demo برای Multi-Branch
Branch dashboard → common template → comparison.

---

# 14. Persona-specific Objection Handling

### «یک نرم‌افزار دیگر؟»
پاسخ محصول: لایه workflow کنار سیستم فعلی؛ نه replacement اجباری.

### «تیم استفاده نمی‌کند»
پاسخ: Telegram-first، setup محدود، 2 workflow در Pilot، adoption measurement.

### «وقت ثبت نداریم»
پاسخ: template، voice، default field و quick action.

### «اطلاعات بیمار چه می‌شود؟»
پاسخ: حداقل داده، role-based access، audit، privacy-by-design و scope روشن.

### «من پزشکم، task manager نمی‌خواهم»
پاسخ: پزشک فقط assign/approve/exception؛ مدیریت روزمره برای staff است.

---

# 15. Anti-Persona

برای شروع، این خریداران اولویت پایین دارند:

- فردی که تنها مسئله‌اش calendar است؛
- مالک کاملاً غایب بدون champion داخلی؛
- سازمانی که فقط پروژه سفارشی می‌خواهد؛
- مدیری که هدف اصلی‌اش surveillance کارکنان است؛
- پزشکی که هر ابزار غیرکلینیکی را رد می‌کند؛
- مرکزی که حاضر نیست workflow فعلی خود را شفاف کند.

---

# 16. تصمیم طراحی حاصل از Personaها

1. Telegram-first برای frontline.
2. Web-first برای manager/owner.
3. پزشک باید کمترین interaction را داشته باشد.
4. follow-up coordinator نیازمند queue و next action است.
5. performance features نباید در ابتدا حس surveillance ایجاد کنند.
6. onboarding باید role-based باشد.
7. notification باید قابل تنظیم باشد.
8. data entry باید حداقلی باشد.
9. هر Persona dashboard متفاوت نیاز دارد.
10. permission و audit برای توسعه به multi-branch ضروری‌اند.
