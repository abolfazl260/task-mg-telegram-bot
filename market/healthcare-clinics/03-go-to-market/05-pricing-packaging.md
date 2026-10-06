# قیمت‌گذاری و بسته‌بندی — Healthcare Clinics

> وضعیت سند: Pricing Hypothesis v1  
> نکته: جغرافیای فروش نهایی نشده است؛ بنابراین قیمت‌های TaskMG در این سند **فرضیه آزمایشی** هستند، نه Price List قطعی.  
> اصل: Pricing باید با Value، Complexity، Location Count و Implementation Cost هم‌راستا باشد؛ نه فقط تعداد User.

---

# 1. هدف Pricing

مدل قیمت‌گذاری باید:

- برای کلینیک قابل فهم باشد؛
- با رشد customer افزایش یابد؛
- هزینه support/customization را پوشش دهد؛
- adoption را با per-user tax خراب نکند؛
- multi-branch expansion را monetize کند؛
- integration و professional services را رایگان فرض نکند.

---

# 2. Benchmark بازار

نمونه‌های عمومی 2026 نشان می‌دهد مدل‌های مختلفی در بازار dental software وجود دارند:

## Open Dental

در آمریکا، Software License and Support از حدود **$199/month per location** برای تا 3 provider شروع می‌شود و پس از دوره اولیه نرخ متفاوت دارد. سرویس‌های اضافی مثل eServices جدا قیمت‌گذاری می‌شوند.

Official:
https://www.opendental.com/site/fees.html

## CareStack

Essentials از حدود **$829/month** و Intelligence از حدود **$1,299/month** شروع می‌شود. قیمت بر اساس عواملی مثل locations/providers/chairs نیز تنظیم می‌شود.

Official:
https://carestack.com/pricing

## NexHealth

Pricing به‌صورت package/product selection و quote برای practice ارائه می‌شود.

Official:
https://www.nexhealth.com/pricing

## نتیجه Benchmark

TaskMG نباید با full PMS price parity شروع کند، چون scope متفاوت است. اما بازار نشان می‌دهد:

- per-location
- package-based
- provider/location-adjusted
- implementation fee
- add-on pricing

مدل‌های قابل قبول هستند.

---

# 3. Pricing Position

TaskMG:

- ارزان‌ترین task manager نیست؛
- Patient Record و Session management را در خود دارد؛
- علاوه بر record keeping، یک operational workflow layer است.

بنابراین price anchor باید بین:

**Horizontal SaaS Tool**

و

**Full Practice Management Platform**

قرار گیرد، بر اساس Value واقعی customer.

---

# 4. Pricing Metric

## Primary Metric پیشنهادی

**Per Clinic / Location**

چرا؟

- ساده است؛
- با business unit align است؛
- user growth را penalize نمی‌کند؛
- با market convention سازگار است.

## Secondary Adjusters

- number of locations
- workflow package
- integration complexity
- support tier

## Avoid as Primary

Per-task:
پیچیده و ضد adoption.

Pure per-user:
ممکن است clinic را از اضافه‌کردن staff منصرف کند.

---

# 5. Packaging Principles

## Principle 1

Core workflow value در plan پایه وجود داشته باشد.

## Principle 2

Security/RBAC feature نباید paywall خطرناک باشد.

## Principle 3

Advanced automation/reporting/integrations می‌توانند tier differentiator باشند.

## Principle 4

Professional Services جدا از SaaS subscription باشد.

---

# 6. Starter Plan — Hypothesis

## Target

- small clinic
- 1 location
- 2-5 providers
- simple workflows

## Included

- Telegram
- Web
- tasks
- roles
- complete patient records
- follow-up queue
- basic templates
- reminders
- basic dashboard
- CSV export
- standard support

## Limits

ممکن است محدودیت روی:
- workflows
- automation rules
- advanced reports

باشد، نه روی essential users.

## Initial Test Range

**USD $79–149 / location / month**

فقط برای WTP test؛ نه final published price.

---

# 7. Clinic Plan — Hypothesis

## Target

ICP اصلی.

## Included

Starter +

- configurable workflows
- advanced follow-up
- outcome/next action
- manager dashboard
- recurring workflows
- basic AI/voice
- advanced reports
- audit viewer
- basic integration capability

## Initial Test Range

**USD $199–399 / location / month**

این range باید با geography و Pilot data validate شود.

---

# 8. Multi-Branch Plan — Hypothesis

## Target

2+ locations.

## Included

Clinic +

- centralized admin
- central templates
- cross-branch dashboard
- branch comparison
- broader permissions
- rollout support

## Pricing Shape

مثال:

Base organization fee  
+ per active location fee

## Test Range

نه یک عدد ثابت؛ quote بر اساس:

- branches
- implementation
- integration
- reporting needs

---

# 9. Enterprise / Custom Plan

## Target

- large groups
- complex security
- enterprise procurement
- custom integrations

## Included

- negotiated SLA
- implementation project
- advanced audit
- SSO future
- integration package
- dedicated success plan

## Pricing

Annual contract / custom quote.

---

# 10. Free Plan

## Recommendation

فعلاً **No Permanent Free Plan**.

دلیل:

- onboarding/support intensive
- B2B workflow product
- data/security responsibility
- high-touch setup

## Alternative

- sandbox demo
- limited trial
- workflow audit

---

# 11. Trial

## Option A — No Trial, Pilot

برای current motion بهتر.

## Option B — 14/30-day Trial

فقط بعد از self-service onboarding mature.

## Rule

Trial بدون setup success likely misleading است.

---

# 12. Pilot Pricing

Pilot باید commitment ایجاد کند.

## Option 1 — Paid Pilot

Recommended.

مثال structure:

- fixed setup/pilot fee
- limited workflows
- defined duration
- conversion credit optional

## Option 2 — Discounted Pilot

اگر strategic.

## Option 3 — Free

فقط exception:
- major learning value
- strong reference potential
- signed decision criteria

---

# 13. Setup Fee

Setup work ممکن است شامل:

- clinic configuration
- roles
- workflow mapping
- templates
- import
- training

## Why Charge

Setup labor واقعی است و customer commitment می‌سازد.

## Test Range

Small:
**$200–750 one-time**

Medium/custom:
**$750–3,000+**

جغرافیا و complexity تعیین‌کننده‌اند.

---

# 14. Customization Fee

## Included Configuration

- labels
- standard template settings
- role mapping

ممکن است در setup شامل شود.

## Billable Customization

- custom workflow
- custom report
- custom field set
- custom connector

## Pricing Model

- fixed scope project
- hourly/day rate
- package

Avoid:
unlimited customization subscription.

---

# 15. Integration Fee

Integration هزینه دو نوع دارد:

## One-time

- setup
- mapping
- testing
- migration

## Recurring

- connector maintenance
- API cost
- provider fee
- monitoring

## Rule

third-party usage cost transparent باشد.

---

# 16. AI Pricing

در MVP AI نباید pricing complexity ایجاد کند.

## Initial

fair-use included in Clinic plan.

## Later

اگر cost material شد:

- included allowance
- usage add-on
- premium AI tier

## Avoid

per-prompt pricing visible to frontline.

---

# 17. Messaging/SMS Pricing

SMS/WhatsApp third-party cost:

- pass-through
- bundled allowance
- markup transparent

بهتر است usage-heavy communication از core subscription جدا باشد.

---

# 18. Support Packages

## Standard

- knowledge base
- business-hours support
- standard response target

## Priority

- faster response
- onboarding sessions
- quarterly review

## Enterprise

- negotiated SLA
- named contact
- escalation process

---

# 19. Annual vs Monthly

## Monthly

- lower commitment
- higher price

## Annual

- discount
- lower churn
- upfront cash

## Initial Discount Hypothesis

Annual prepay:
**10–15%**

با market test validate شود.

---

# 20. Discount Strategy

Allowed:

- annual prepay
- multi-location
- early design partner
- strategic reference

## Not Allowed

- arbitrary sales discount
- permanent founder discount
- discount without expiry

هر discount:

- reason
- approver
- expiry

---

# 21. Early Adopter Pricing

Early customers می‌توانند:

- price protection limited period
- discounted setup
- additional support

بگیرند.

اما قرارداد "lifetime low price" توصیه نمی‌شود.

---

# 22. Willingness to Pay Research

## Van Westendorp Questions

برای customer:

- چه قیمتی آن‌قدر ارزان است که کیفیت را زیر سؤال ببرید؟
- چه قیمتی bargain است؟
- چه قیمتی گران ولی قابل بررسی است؟
- چه قیمتی غیرقابل قبول است؟

## Better

همراه با concrete package/demo پرسیده شود.

---

# 23. Price Sensitivity Test

در proposals اولیه، quoteها را systematic test کنیم.

مثال:

Cohort A:
lower range.

Cohort B:
middle.

Cohort C:
higher with stronger service.

نه random negotiation.

---

# 24. Value Metric Research

بررسی شود کدام metric customer آن را fair می‌داند:

- location
- provider
- active staff
- workflow volume

Recommendation اولیه:
**Location first.**

---

# 25. Packaging Matrix

| Capability | Starter | Clinic | Multi-Branch |
|---|---|---|---|
| Tasks | ✓ | ✓ | ✓ |
| Patient Reference | ✓ | ✓ | ✓ |
| Follow-up Queue | ✓ | ✓ | ✓ |
| Basic Templates | ✓ | ✓ | ✓ |
| Advanced Workflows | Limited | ✓ | ✓ |
| AI/Voice | Limited | ✓ | ✓ |
| Reports | Basic | Advanced | Advanced |
| Audit | ✓ | ✓ | ✓ |
| Integrations | Basic | Add-on/Included | Advanced |
| Central Branch Admin | — | — | ✓ |
| Priority Support | Add-on | Add-on | Included/Custom |

---

# 26. Packaging Anti-Patterns

نباید:

- permission/security را حذف کنیم تا customer upgrade کند؛
- per-user charge شدید بگذاریم؛
- 10 plan بسازیم؛
- add-onها را مبهم کنیم؛
- implementation را "free" فرض کنیم.

---

# 27. Unit Economics Inputs

Pricing نهایی باید این‌ها را پوشش دهد:

- hosting
- AI usage
- messaging cost
- support
- onboarding
- payment fees
- engineering maintenance
- partner commissions

---

# 28. Gross Margin

SaaS gross margin باید monitor شود.

اگر implementation سنگین است، services margin جدا track شود.

## Revenue Types

- Subscription
- Setup
- Customization
- Integration
- Support
- Usage

---

# 29. CAC Payback

Pricing باید با channel CAC سازگار باشد.

Formula:

**CAC Payback Months = CAC / Monthly Gross Profit**

هدف دقیق بعد از data واقعی تعیین شود.

---

# 30. LTV

Early stage LTV را با فرض‌های خوش‌بینانه نسازیم.

Track:

- logo retention
- revenue retention
- expansion
- gross margin

سپس LTV model.

---

# 31. Pricing for Multi-Branch

Volume discount منطقی است، اما price باید با central value رشد کند.

مثال structure:

- first location full price
- additional location lower unit rate
- organization/admin fee optional

Avoid:
"same price unlimited locations".

---

# 32. Currency & Localization

Pricing باید بر اساس geography:

- local purchasing power
- tax
- payment methods
- FX risk
- support cost

localize شود.

USD benchmark فقط reference است.

---

# 33. Taxes

Published price باید مشخص کند:

- tax included/excluded
- invoice rules
- local VAT/GST implications

legal/accounting review per country.

---

# 34. Contract Terms

Recommended starting point:

- monthly or annual
- auto-renewal transparent
- cancellation terms
- data export
- data deletion/retention
- support scope

---

# 35. Pricing Page Strategy

در SMB market، transparent "starting at" می‌تواند qualification را بهتر کند.

اما تا زمانی که:

- package stable نیست
- geography unknown
- implementation variable است

می‌توان از:
**Starting at / Contact for clinic pricing**

استفاده کرد.

---

# 36. Proposal Pricing

Proposal باید جدا نشان دهد:

1. Subscription
2. Setup
3. Add-ons
4. Third-party fees
5. Discount
6. Total First Year
7. Renewal Price

---

# 37. Price Increase Policy

در future:

- predictable
- advance notice
- contract-respecting
- not arbitrary

Early adopter commitments مستند باشند.

---

# 38. Pricing Metrics

- ARPA
- ACV
- discount rate
- gross margin
- plan mix
- pilot-to-paid
- setup margin
- expansion MRR
- price objection rate

---

# 39. Pricing Validation Gate

قبل از public fixed pricing:

- حداقل 10-15 serious pricing conversations
- 3+ paid customers
- known onboarding cost
- known support load
- clear plan boundaries

---

# 40. Current Recommendation

فعلاً:

- **Per-location subscription**
- **Starter / Clinic / Multi-Branch**
- **One-time setup fee**
- **Integration/customization separately**
- **Annual discount**
- **No permanent free plan**
- **Paid or committed Pilot**

Price ranges این سند برای **testing** هستند و بعد از انتخاب geography و WTP research باید بازبینی شوند.
