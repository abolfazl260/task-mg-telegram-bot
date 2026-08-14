# معرفی TaskBot

TaskBot یک ربات فارسی‌محور مدیریت وظایف در Telegram است که ایجاد، پیگیری، واگذاری، گزارش‌گیری و مدیریت عادت‌ها را در یک محیط یکپارچه ارائه می‌کند.

## قابلیت‌های اصلی

- ایجاد و مدیریت تسک
- اولویت، ددلاین، دسته‌بندی و تگ
- وضعیت‌های در انتظار، در حال انجام، انجام‌شده و لغوشده
- تعیین مسئول و برعهده گرفتن تسک
- تیم و اعضای هم‌تیمی
- کامنت و تاریخچه واگذاری
- فیلتر و صفحه‌بندی تسک‌ها
- Mini Dashboard
- گزارش و خروجی CSV/Excel
- ورود گروهی CSV با اعتبارسنجی و Preview
- تاریخ جلالی
- مدیریت عادت
- دستیار هوشمند با Groq
- اتصال Jira
- اتصال سرویس‌های مدیریت کار خارجی
- Guest Mode
- Telegram Business / Secretary Mode
- Telegram Stars
- Multi-Bot
- ساخت ربات اختصاصی
- گزارش‌های تحت وب

## معماری کلی

```text
Telegram
   ↓
Handlers
   ↓
Services
   ↓
SQLite / aiosqlite
   ↓
Reports / Integrations / Web
```

رابط کاربری اصلی برای کاربر فارسی است و بخش زیادی از تعامل از طریق Inline Keyboard انجام می‌شود.

## مستندات

- [نصب و اجرای پروژه](02-installation.md)
- [تنظیمات و متغیرهای محیطی](03-configuration.md)
- [مدیریت تسک‌ها](04-task-management.md)
- [گزارش‌ها و ورود اطلاعات](05-reports-and-import.md)
- [یکپارچه‌سازی‌ها](06-integrations.md)
- [Multi-Bot و Business Mode](07-bots-and-business.md)
- [معماری و ساختار کد](08-architecture.md)
- [امنیت و عملیات](09-security-and-operations.md)
- [راهنمای توسعه](10-development.md)
- [ماتریس قابلیت‌ها](FEATURE_MATRIX.md)
- [ورودی صوتی](voice-input.md)
- [استقرار Web App](webapp-deployment.md)
