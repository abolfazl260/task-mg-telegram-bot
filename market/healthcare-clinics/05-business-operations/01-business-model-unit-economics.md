# مدل کسب‌وکار و Unit Economics — Healthcare Clinics

> وضعیت سند: Business Model v1  
> Vertical: Healthcare Clinics  
> Beachhead: کلینیک‌های خصوصی دندان‌پزشکی چندپزشکه  
> اصل: مدل درآمد باید با **Operational Value** و کاهش chaos/پیگیری از دست‌رفته هم‌راستا باشد، نه صرفاً تعداد Feature.

---

# 1. مدل کسب‌وکار

مدل پیشنهادی یک SaaS عمودی با ترکیب درآمد تکرارشونده و خدمات راه‌اندازی است:

1. **Subscription Revenue**
2. **Setup / Implementation Revenue**
3. **Customization Revenue**
4. **Integration Revenue**
5. **Premium Support Revenue**
6. **Expansion Revenue**

هسته اقتصادی باید از Subscription سودآور شود؛ خدمات حرفه‌ای نباید تنها راه سوددهی باشند.

---

# 2. Customer Value Model

مشتری بابت «Task Management» پول نمی‌دهد. ارزش اقتصادی باید به یکی از این موارد متصل شود:

- کاهش missed follow-up
- کاهش زمان coordination
- کاهش status chasing
- کاهش dependency به افراد
- افزایش visibility مدیر
- افزایش consistency بین شیفت‌ها
- استانداردسازی workflow
- افزایش recovery فرصت‌های درمانی
- کاهش دوباره‌کاری
- آماده‌شدن برای چندشعبه

---

# 3. Revenue Model

## 3.1 Recurring SaaS

پیشنهاد پایه:

**Base Clinic Fee + Included Users + Add-on Users/Branches/Capabilities**

چرا؟

- فقط per-user pricing می‌تواند reception-heavy clinic را penalize کند.
- فقط flat fee با رشد مشتری capture value نمی‌کند.
- Hybrid pricing با scale سازمان بهتر هم‌راستا است.

---

# 4. Pricing Metric

Pricing metric باید چیزی باشد که:

- قابل فهم باشد؛
- با value رشد کند؛
- قابل اندازه‌گیری باشد؛
- باعث رفتار مصنوعی نشود.

## Candidate Metrics

### Active Staff
مزیت:
ساده و استاندارد.

ریسک:
clinic ممکن است staff login را share کند.

### Branch
مزیت:
برای multi-location واضح.

ریسک:
برای clinic تک‌شعبه value differentiation کم است.

### Active Workflow
مزیت:
مستقیماً با value مرتبط.

ریسک:
برای sales پیچیده‌تر.

### Patient Volume
ریسک بالا:
ممکن است حساسیت privacy و perception نامناسب ایجاد کند.

## Recommendation

**Primary: Clinic + Staff Tier**  
**Expansion: Branch + Advanced Modules**

---

# 5. Packaging Hypothesis

این بسته‌ها فرضیه اولیه هستند و باید با Pricing Interview و Pilot validate شوند.

## Starter

مناسب:
- small clinic
- یک شعبه
- تیم کوچک

شامل:
- Task
- Follow-up
- 5 workflow templates
- Telegram
- Basic Web Dashboard
- Standard Reports
- Standard Support

---

## Clinic

مناسب:
- چند پزشک
- manager/coordinator
- workflow پرتکرار

شامل Starter +
- configurable workflows
- advanced reports
- audit
- role configuration
- recurring workflow
- AI/voice package محدود
- calendar integration پایه

---

## Multi-Branch

شامل Clinic +
- branch hierarchy
- central templates
- consolidated reporting
- cross-branch roles
- advanced audit
- priority support

---

## Enterprise / Custom

برای:
- network
- complex integration
- SSO/security requirements
- contractual SLA

Pricing:
quote-based.

---

# 6. Subscription Revenue

فرمول:

**MRR = Active Paid Clinics × Average MRR per Clinic**

**ARR = MRR × 12**

Segment شود بر اساس:

- Starter
- Clinic
- Multi-Branch
- Enterprise

همچنین:

- New MRR
- Expansion MRR
- Contraction MRR
- Churned MRR

جدا اندازه‌گیری شوند.

---

# 7. Setup Revenue

Setup برای Vertical Healthcare منطقی است چون ارزش از configuration و adoption می‌آید.

شامل:

- discovery workshop
- clinic setup
- role setup
- import
- 2 workflow configuration
- onboarding/training
- go-live support

## Rule

Setup fee باید delivery cost را پوشش دهد و customer commitment ایجاد کند، اما barrier بیش از حد نسازد.

---

# 8. Customization Revenue

Customization فقط برای مواردی charge شود که از Standard Configuration خارج‌اند.

## Standard Configuration — Included / Low Cost

- terminology
- role assignment
- template timing
- standard fields
- standard reports

## Paid Customization

- non-standard workflow
- unique report
- advanced data migration
- custom automation
- custom branding beyond package

## Avoid

customer-specific source-code fork.

---

# 9. Integration Revenue

Integration سه مدل دارد:

## Standard Connector
Recurring add-on یا plan feature.

## Setup Fee
برای connection/configuration.

## Custom Connector
Project fee + maintenance fee.

## Rule

اگر connector برای چند مشتری reusable شد، باید از custom project به productized connector تبدیل شود.

---

# 10. Support Revenue

Standard support داخل subscription.

Premium support می‌تواند شامل:

- faster SLA
- dedicated success contact
- quarterly operational review
- custom training
- branch rollout support
- priority incident handling

---

# 11. Professional Services Boundary

Professional Services نباید:

- feature gap دائمی را پنهان کند؛
- هر customer را پروژه نرم‌افزاری کند؛
- recurring gross margin را تخریب کند.

هدف:

**Services accelerate Time-to-Value; Product delivers recurring value.**

---

# 12. Revenue Mix Target

در مراحل اولیه ممکن است Setup سهم بالاتری داشته باشد.

در maturity مطلوب:

- majority revenue = recurring subscription
- services = onboarding/expansion accelerator
- custom development = minority and strategic only

عدد دقیق پس از 10 تا 20 مشتری پولی تعیین شود.

---

# 13. CAC

**CAC = Total Sales & Marketing Cost / New Customers Acquired**

در مرحله founder-led sales، CAC واقعی باید شامل این موارد شود:

- founder sales time
- demo time
- travel if any
- marketing spend
- SDR/sales compensation
- tools
- event cost
- pilot delivery cost غیرقابل بازیافت

## Blended CAC

کل acquisition cost.

## Paid CAC

فقط کانال پولی.

## Sales-assisted CAC

برای clinic SaaS مهم‌تر است.

---

# 14. CAC by Channel

برای هر channel جدا:

- outbound
- referral
- partner
- events
- paid search
- content/inbound
- consultant/channel partner

اندازه‌گیری:

**Channel CAC = Channel Spend + Allocated Sales Cost / Customers Won**

---

# 15. Cost of Goods Sold — COGS

برای SaaS:

- cloud infrastructure
- database
- storage
- Telegram/communication variable costs
- AI inference
- transcription
- email/SMS/WhatsApp variable costs
- third-party API fees
- production support directly attributable
- payment processing where applicable

Professional services delivery در تحلیل جدا هم دیده شود.

---

# 16. Gross Margin

**Gross Margin = (Revenue - COGS) / Revenue**

Gross margin باید دو view داشته باشد:

## Software Gross Margin

Subscription revenue vs technical/service delivery COGS.

## Blended Gross Margin

همراه setup/support/customization.

اگر customization بالا باشد، blended margin ممکن است تصویر SaaS را مخدوش کند.

---

# 17. Contribution Margin

برای هر customer:

**Contribution = Revenue - Variable Infrastructure - Variable Messaging/AI - Direct Support - Direct Success Cost**

این metric برای فهمیدن «مشتری واقعاً سودآور است یا فقط revenue دارد» ضروری است.

---

# 18. LTV

مدل ساده:

**LTV ≈ ARPA × Gross Margin % / Monthly Logo Churn**

برای داده کم، این مدل بسیار حساس و potentially misleading است.

## در Early Stage

بهتر است به‌جای LTV دقیق:

- 12-month gross profit
- cohort retention
- expansion behavior

استفاده شود.

LTV زمانی قابل اتکاتر است که retention history کافی داشته باشیم.

---

# 19. LTV:CAC

هدف بلندمدت SaaS باید LTV:CAC سالم باشد، اما قبل از داده واقعی نباید عدد industry benchmark را قانون بدانیم.

Working interpretation:

- <1:1 → مدل اقتصادی ناسالم
- نزدیک 1:1 تا 2:1 → نیازمند بررسی
- بالاتر → بهتر، با توجه به growth و payback

Target رسمی بعد از data واقعی تعیین شود.

---

# 20. CAC Payback

**CAC Payback Months = CAC / Monthly Gross Profit per Customer**

Monthly Gross Profit:

**ARPA × Gross Margin %**

Payback یکی از مهم‌ترین metricها برای رشد است.

---

# 21. ARPA

**Average Revenue Per Account**

Segment شود:

- Small Dental
- Medium Dental
- Multi-Branch
- Beauty/Other Vertical later

ARPA باید همراه:

- user count
- branch count
- workflow count
- support tier

تحلیل شود.

---

# 22. Logo Churn

**Logo Churn = Customers Lost / Customers at Start of Period**

Lost customer reason ثبت شود:

- no adoption
- price
- champion left
- integration gap
- product gap
- closed business
- security/compliance
- competitor

---

# 23. Revenue Churn

Logo churn کافی نیست.

**Gross Revenue Retention (GRR)**

درآمد شروع دوره پس از churn/contraction، بدون expansion.

**Net Revenue Retention (NRR)**

GRR + expansion.

Multi-branch strategy باید در بلندمدت NRR را تقویت کند.

---

# 24. Expansion Revenue

Expansion مسیر اصلی رشد داخل account است.

## Expansion Paths

- more staff
- more branch
- more workflow
- premium reporting
- integrations
- AI package
- premium support
- new department

---

# 25. Land-and-Expand Strategy

Land:

- 1 branch
- 2 workflows
- 5–15 users

Expand:

- more workflows
- entire clinic
- branch 2
- central operations

این مدل ریسک خرید اولیه را کاهش می‌دهد.

---

# 26. Implementation Cost

برای هر onboarding اندازه‌گیری شود:

- hours discovery
- configuration hours
- migration hours
- training hours
- support first 30 days

Metric:

**Implementation Cost per Clinic**

هدف:
کاهش با template و standardization.

---

# 27. Time-to-Value Economics

هرچه onboarding طولانی‌تر:

- implementation cost بالاتر
- churn risk بالاتر
- cash conversion ضعیف‌تر

بنابراین:

**Time-to-First-Value** یک metric مالی هم هست.

---

# 28. Support Cost

اندازه‌گیری:

- tickets per clinic
- support minutes
- severity
- repeat issue
- onboarding vs steady-state

High-support customer باید بررسی شود:

- UX problem؟
- training gap؟
- product bug؟
- wrong ICP؟

---

# 29. AI Unit Cost

AI باید جدا track شود:

- cost per AI-active clinic
- cost per task extraction
- cost per transcription minute
- cost per manager brief

اگر AI add-on نیست، باید در gross margin دیده شود.

---

# 30. Messaging Unit Cost

SMS/WhatsApp ممکن است COGS متغیر بزرگی شود.

مدل pricing باید:

- included quota
- pass-through
- add-on
- fair-use

را بررسی کند.

---

# 31. Pilot Economics

Pilot باید یکی از این مدل‌ها باشد:

## Paid Pilot
ترجیحی.

## Credited Pilot
هزینه Pilot در قرارداد annual credit شود.

## Free Pilot
فقط اگر:
- strategic logo
- learning value بالا
- fixed scope
- fixed end date
- buyer committed

Pilot بی‌انتها ممنوع.

---

# 32. Annual vs Monthly

## Annual

مزایا:
- cash upfront
- churn lower
- commitment
- implementation justification

## Monthly

مزایا:
- lower barrier
- SMB-friendly

## Recommendation

Monthly option + annual incentive.

برای setup-heavy customer، annual منطقی‌تر است.

---

# 33. Discount Policy

Discount باید:

- مدت مشخص
- reason code
- approval
- expiry

داشته باشد.

Avoid:

- permanent custom discount
- untracked founder deal
- discount without term commitment

---

# 34. Pricing Research

قبل از نهایی‌سازی:

- 10+ willingness-to-pay interviews
- lost deal price reason
- competitor pricing where public
- package preference
- setup fee reaction
- annual discount reaction

Methods:

- direct price discussion
- Van Westendorp as supporting tool
- package trade-off
- paid pilot conversion

---

# 35. Unit Economics Dashboard

حداقل:

- MRR
- ARR
- ARPA
- New MRR
- Expansion MRR
- Churned MRR
- GRR
- NRR
- CAC
- CAC Payback
- Gross Margin
- Implementation Cost
- Support Cost per Account
- AI Cost per Account

---

# 36. Scenario Model

سه Scenario لازم است:

## Conservative

- lower ARPA
- slower sales
- higher support
- higher churn

## Base

validated assumptions.

## Upside

- higher expansion
- better referral
- multi-branch

مدل مالی باید assumption-driven باشد، نه یک forecast ثابت.

---

# 37. Unit Economics Assumptions Register

برای هر assumption:

- assumption
- current estimate
- evidence level
- source
- owner
- next validation date

مثال:

- Average onboarding hours
- Monthly support cost
- Pilot-to-paid rate
- Logo churn
- Expansion rate
- ARPA

---

# 38. Economic Guardrails

Account نباید به‌صورت پیش‌فرض پذیرفته شود اگر:

- customization cost بسیار بالا
- integration یک‌بارمصرف
- support requirement خارج از package
- contract value پایین‌تر از delivery cost
- compliance requirement غیرقابل پشتیبانی

---

# 39. Early-stage Targets

تا قبل از داده کافی، targetها باید به‌صورت **validation target** تعریف شوند، نه benchmark قطعی.

نمونه:

- Pilot → Paid conversion trend
- Time-to-Value کاهش یابد
- Implementation hours per clinic کاهش یابد
- Gross margin با scale بهتر شود
- Expansion در accountهای موفق دیده شود
- retention در ICP بهتر از non-ICP باشد

---

# 40. Definition of Healthy Business Model

مدل زمانی در مسیر درست است که:

1. subscription بخش اصلی revenue شود؛
2. onboarding با template قابل تکرار شود؛
3. support cost بعد از ماه اول کاهش یابد؛
4. ICP customer retention بهتری داشته باشد؛
5. expansion واقعی رخ دهد؛
6. custom development minority باشد؛
7. CAC payback با رشد قابل تحمل باشد؛
8. gross margin با افزایش customer خراب نشود.

---

# 41. تصمیم فعلی

مدل پیشنهادی:

**Recurring Clinic SaaS + One-time Setup + Productized Add-ons**

و نه:

**Custom Software Project per Clinic**

موفقیت اقتصادی TaskMG به productization workflowها و کاهش implementation cost وابسته است.
