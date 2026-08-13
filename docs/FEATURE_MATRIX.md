# Feature Matrix — Task Manager Telegram Bot

> مرجع مرکزی قابلیت‌های قابل تخصیص به هر Bot Profile. این سند مبنای طراحی سیستم ماژولار چندباته است و باید هنگام اضافه‌شدن قابلیت جدید به‌روزرسانی شود.

## 1. اصول ماتریس

- هر قابلیت باید تا حد امکان مستقل از سایر قابلیت‌ها قابل فعال/غیرفعال شدن باشد.
- `Feature` مشخص می‌کند یک حوزه فعال است؛ `Permission` مشخص می‌کند دقیقاً چه عملی مجاز است.
- `View` و `Manage` از هم جدا در نظر گرفته می‌شوند تا یک بات بتواند فقط خواندنی باشد.
- قابلیت‌های AI و Voice نیز باید به حوزه عملیاتی خود محدود شوند؛ مثلاً AI در بات Habit Only نباید مسیر ایجاد Task تولید کند.
- `Core` قابلیت‌های پایه مانند `/start` و `/help` هستند و نباید با Task/Habit اشتباه گرفته شوند.

## 2. ماتریس سطح Feature

| حوزه | کلید پیشنهادی | توضیح | وابستگی اصلی |
|---|---|---|---|
| هسته بات | `core` | start، help، settings و منوی پایه | — |
| تسک‌ها | `tasks` | چرخه کامل مدیریت تسک | core |
| عادت‌ها | `habits` | ایجاد و مدیریت عادت | core |
| تیم‌ها | `teams` | تیم و اعضای تیم | core |
| مسئول تسک | `assignment` | تعیین/تغییر مسئول و برعهده گرفتن | tasks، teams در حالت تیمی |
| کامنت | `comments` | ثبت و مشاهده نظر روی تسک | tasks |
| فایل و پیوست | `attachments` | عکس، فایل، صوت و سایر پیوست‌ها | tasks/comments |
| تگ | `tags` | ایجاد و انتخاب تگ | tasks، habits در صورت پشتیبانی |
| دسته‌بندی | `categories` | دسته‌بندی موجودیت‌ها | tasks، habits |
| اولویت | `priority` | تعیین و تغییر اولویت | tasks |
| موعد | `deadline` | تاریخ و ساعت موعد | tasks |
| جستجو | `search` | جستجوی داده‌ها | entity مورد جستجو |
| گزارشات | `reports` | داشبورد و گزارش‌های تحلیلی | داده متناظر |
| هوش مصنوعی | `ai` | درک زبان طبیعی و اجرای عملیات | محدود به domain مجاز |
| صوت | `voice` | دریافت درخواست صوتی | ai یا handler متن |
| تمپلیت‌ها | `templates` | الگوهای آماده | tasks/habits |
| واردسازی گروهی | `bulk_import` | ورود چند داده از فایل | entity متناظر |
| یکپارچه‌سازی | `integrations` | سرویس‌های خارجی | core |
| حالت مهمان | `guest_mode` | قابلیت‌های قبل از ثبت‌نام/ورود | core |
| ارتباط با ما | `contact` | ارتباط کاربر با مدیر/پشتیبانی | core |
| پرداخت/حمایت | `donate` | حمایت مالی یا پرداخت | core |
| ربات‌های سفارشی | `custom_bots` | مدیریت Bot Profileهای دیگر | admin |

## 3. مدیریت Task — ماتریس Permission

| Permission | شرح | وابستگی |
|---|---|---|
| `tasks.view` | مشاهده تسک‌های مجاز | tasks |
| `tasks.create` | ایجاد تسک | tasks |
| `tasks.edit` | ویرایش عنوان و جزئیات | tasks |
| `tasks.delete` | حذف تسک | tasks |
| `tasks.status` | تغییر وضعیت | tasks |
| `tasks.complete` | تکمیل تسک | tasks |
| `tasks.cancel` | لغو تسک | tasks |
| `tasks.restore` | بازگردانی تسک | tasks |
| `tasks.bulk_create` | ایجاد چند تسک | tasks، bulk_import |
| `tasks.export` | خروجی گرفتن از تسک‌ها | tasks |

## 4. مسئول / Assignment

| Permission | شرح | وابستگی |
|---|---|---|
| `assignment.view` | مشاهده مسئول فعلی | tasks |
| `assignment.assign` | تعیین مسئول | tasks |
| `assignment.reassign` | تغییر مسئول | assignment |
| `assignment.claim` | برعهده گرفتن تسک بدون مسئول | assignment |
| `assignment.unassign` | حذف مسئول | assignment |
| `assignment.team_scope` | محدودکردن انتخاب مسئول به اعضای مرتبط تیم | assignment، teams |

## 5. کامنت و پیوست

| Permission | شرح | وابستگی |
|---|---|---|
| `comments.view` | مشاهده کامنت‌ها | comments |
| `comments.create` | افزودن کامنت متنی | comments |
| `comments.edit` | ویرایش کامنت خود کاربر | comments |
| `comments.delete` | حذف کامنت مجاز | comments |
| `attachments.view` | مشاهده فایل‌های پیوست | attachments |
| `attachments.upload` | ارسال عکس، فایل، صوت و سایر انواع پشتیبانی‌شده | attachments |
| `attachments.delete` | حذف پیوست مجاز | attachments |

## 6. Metadata تسک

| حوزه | Permission | شرح |
|---|---|---|
| تگ | `tags.view` | مشاهده تگ‌ها |
| تگ | `tags.create` | ایجاد تگ |
| تگ | `tags.assign` | اتصال تگ به تسک |
| تگ | `tags.edit` | ویرایش تگ |
| دسته | `categories.view` | مشاهده دسته‌ها |
| دسته | `categories.create` | ایجاد دسته |
| دسته | `categories.assign` | اتصال دسته |
| دسته | `categories.edit` | ویرایش دسته |
| اولویت | `priority.view` | مشاهده اولویت |
| اولویت | `priority.set` | تعیین/تغییر اولویت |
| موعد | `deadline.view` | مشاهده موعد |
| موعد | `deadline.set` | تعیین تاریخ و ساعت |
| یادآوری | `reminders.view` | مشاهده یادآوری |
| یادآوری | `reminders.manage` | ایجاد/ویرایش/حذف یادآوری |

## 7. تیم‌ها

| Permission | شرح |
|---|---|
| `teams.view` | مشاهده تیم‌ها |
| `teams.create` | ایجاد تیم |
| `teams.edit` | ویرایش تیم |
| `teams.delete` | حذف تیم |
| `teams.members.view` | مشاهده اعضا |
| `teams.members.add` | افزودن عضو |
| `teams.members.remove` | حذف عضو |
| `teams.members.manage` | مدیریت عضویت و نقش‌ها |
| `teams.tasks.view` | مشاهده تسک‌های تیم |
| `teams.tasks.assign` | تخصیص تسک در محدوده تیم |
| `teams.admin` | مدیریت کامل تیم |

## 8. عادت‌ها

| Permission | شرح |
|---|---|
| `habits.view` | مشاهده عادت‌ها |
| `habits.create` | ایجاد عادت |
| `habits.edit` | ویرایش عادت |
| `habits.delete` | حذف عادت |
| `habits.complete` | ثبت انجام عادت |
| `habits.undo_complete` | اصلاح ثبت انجام |
| `habits.reminders.view` | مشاهده یادآوری عادت |
| `habits.reminders.manage` | مدیریت یادآوری عادت |
| `habits.stats.view` | مشاهده آمار و رکوردها |
| `habits.templates.view` | مشاهده قالب‌های آماده عادت |
| `habits.templates.use` | استفاده از قالب آماده |
| `habits.templates.manage` | مدیریت قالب‌ها در صورت مجاز بودن |

## 9. گزارشات — تفکیک کامل

بهتر است `reports` فقط یک کلید کلی نباشد و هر گزارش Permission مستقل داشته باشد.

### گزارش‌های Task

| Permission | گزارش |
|---|---|
| `reports.tasks.overview` | نمای کلی تسک‌ها |
| `reports.tasks.status` | گزارش بر اساس وضعیت |
| `reports.tasks.priority` | گزارش بر اساس اولویت |
| `reports.tasks.category` | گزارش بر اساس دسته‌بندی |
| `reports.tasks.tags` | گزارش بر اساس تگ |
| `reports.tasks.deadline` | موعدها و تأخیرها |
| `reports.tasks.overdue` | تسک‌های عقب‌افتاده |
| `reports.tasks.completion` | نرخ تکمیل |
| `reports.tasks.daily` | گزارش روزانه |
| `reports.tasks.weekly` | گزارش هفتگی |
| `reports.tasks.monthly` | گزارش ماهانه |
| `reports.tasks.calendar` | نمای تقویمی |
| `reports.tasks.heatmap` | Heatmap فعالیت |
| `reports.tasks.trend` | روند تغییرات |

### گزارش‌های Team / Member

| Permission | گزارش |
|---|---|
| `reports.team.overview` | نمای کلی تیم |
| `reports.team.productivity` | بهره‌وری تیم |
| `reports.team.completion` | نرخ تکمیل تیم |
| `reports.team.overdue` | تأخیرهای تیم |
| `reports.member.overview` | نمای کلی عضو |
| `reports.member.productivity` | عملکرد عضو |
| `reports.member.completion` | نرخ تکمیل عضو |
| `reports.member.workload` | حجم کار عضو |
| `reports.member.comparison` | مقایسه اعضا |

### خروجی گزارش

| Permission | خروجی |
|---|---|
| `reports.export.csv` | خروجی CSV |
| `reports.export.pdf` | خروجی PDF |
| `reports.export.image` | خروجی تصویری |

### گزارش‌های Habit

| Permission | گزارش |
|---|---|
| `reports.habits.overview` | نمای کلی عادت‌ها |
| `reports.habits.completion` | میزان انجام |
| `reports.habits.streak` | رکوردهای پیوسته |
| `reports.habits.daily` | گزارش روزانه |
| `reports.habits.weekly` | گزارش هفتگی |
| `reports.habits.monthly` | گزارش ماهانه |
| `reports.habits.heatmap` | Heatmap عادت |

## 10. AI و Voice

AI باید علاوه بر فعال/غیرفعال شدن، Domain مستقل داشته باشد:

| Permission | شرح |
|---|---|
| `ai.chat` | پاسخ عمومی به سؤال |
| `ai.task` | عملیات AI مربوط به Task |
| `ai.habit` | عملیات AI مربوط به Habit |
| `ai.team` | عملیات AI مربوط به Team در صورت نیاز |
| `ai.reports` | پرسش از گزارشات |
| `ai.voice` | اجرای جریان AI از پیام صوتی |

**قاعده مهم:** در Bot Profile با `ai.habit=true` و `ai.task=false`، AI نباید هیچ `ai_task_*` action یا دکمه ایجاد Task تولید کند.

## 11. مثال Bot Profileها

### Task Manager کامل

```text
Tasks             ✓
Habits            ✓
Teams             ✓
Assignment        ✓
Comments          ✓
Attachments       ✓
Tags              ✓
Categories        ✓
Priority          ✓
Deadline          ✓
Search            ✓
Reports           ✓
AI Task           ✓
AI Habit          ✓
AI Voice          ✓
Templates         ✓
Integrations      ✓
```

### Habit + AI + Team Bot (`@byeeeebot`)

```text
Tasks             ✗
Habits            ✓
Teams             ✓
Assignment        ✗
Comments          ✗
Attachments       ✗
Tags              در صورت نیاز
Reports Task      ✗
Reports Habit     اختیاری
AI Task           ✗
AI Habit          ✓
AI Voice          ✓
Help              ✓
```

### Team / Task Bot

```text
Tasks             ✓
Teams             ✓
Assignment        ✓
Comments          ✓
Attachments       ✓
Tags              ✓
Reports Team      ✓
AI Task           ✓
AI Habit          ✗
```

### Reporting Bot

```text
Tasks View        ✓
Tasks Create      ✗
Reports           ✓
Team Reports      ✓
Member Reports    ✓
PDF Export        ✓
CSV Export        ✓
AI Reports        ✓
```

## 12. وضعیت پیاده‌سازی

| بخش | وضعیت فعلی | هدف |
|---|---|---|
| Feature flags در Bot Profile | موجود | حفظ و گسترش |
| Bot Profile چندگانه | موجود | حفظ |
| Task/Team/Habit به‌صورت Feature | موجود | تبدیل به Permissionهای ریزتر |
| Assignment مستقل | بخشی از Task flow | Feature مستقل |
| Comments مستقل | در پروژه موجود/قابل استفاده | Permission مستقل |
| Attachments | در پروژه موجود | Permission مستقل |
| Reports کلی | موجود | تفکیک به Permissionهای گزارش |
| AI | موجود | تفکیک Domain بر اساس Bot Profile |
| Voice | موجود/در حال توسعه | اتصال به `ai.voice` |
| Habit Only | موجود | حذف کامل مسیرهای Task از AI و UI |

## 13. قواعد طراحی برای توسعه بعدی

1. افزودن Feature جدید نباید Featureهای دیگر را فعال کند.
2. Handler عمومی نباید Callback یک Feature اختصاصی را ببلعد؛ ترتیب و فیلتر Handlerها باید با Feature Matrix هماهنگ باشد.
3. هر Callback حساس باید قبل از اجرا Feature/Permission مربوط را بررسی کند.
4. UI باید از Permissionها ساخته شود؛ دکمه‌ای که Permission ندارد نباید نمایش داده شود.
5. Backend نیز باید Permission را بررسی کند؛ مخفی‌کردن دکمه به‌تنهایی کنترل دسترسی نیست.
6. AI باید قبل از تولید Action، Capabilityهای Bot Profile را بررسی کند.
7. گزارش‌ها باید هم سطح Domain و هم سطح نوع خروجی Permission داشته باشند.
8. تغییر Featureهای یک Bot Profile نباید داده‌های Bot Profile یا دیتابیس سایر بات‌ها را حذف کند.
9. هر Feature جدید باید یک ورودی در این ماتریس داشته باشد.
10. برای قابلیت‌های مشترک، نام Permission باید یکتا، توصیفی و قابل توسعه باشد.
