# Multi-Bot، ربات اختصاصی و Business Mode

## Multi-Bot

پروژه می‌تواند چند Bot Profile را هم‌زمان اجرا کند.

نمونه:

```env
BOT_PROFILES=task_manager,request_workflow
BOT_TASK_MANAGER_TOKEN=123456:AAA...
BOT_TASK_MANAGER_USERNAME=TaskManagerPersian_Bot
BOT_REQUEST_WORKFLOW_TOKEN=987654:BBB...
BOT_REQUEST_WORKFLOW_USERNAME=RequestApproval_Bot
```

پروفایل‌ها در مسیر زیر نگهداری می‌شوند:

```text
bots/
├── task_manager.json
└── request_workflow.json
```

هر Profile می‌تواند تنظیمات و قابلیت‌های مخصوص خود را داشته باشد.

## ربات اختصاصی

فرآیند کلی:

```text
ساخت ربات اختصاصی
↓
انتخاب قابلیت‌ها
↓
ارسال Token از BotFather
↓
ثبت Profile
↓
اجرای ربات
```

Token ربات اختصاصی باید Secret محسوب شود و نباید در Log یا Commit قرار بگیرد.

## Secretary / Business Mode

Business Mode برای Telegram Business Connection استفاده می‌شود.

نمونه پاسخ خودکار:

```text
مشتری: سلام، وضعیت سفارش چیست؟

بات:
پیام شما دریافت شد؛ به‌زودی پاسخ می‌دهیم.
```

تنظیمات پاسخ خودکار:

```env
SECRETARY_AUTO_REPLY_ENABLED=true
SECRETARY_AUTO_REPLY_TEXT=پیام شما دریافت شد؛ به‌زودی پاسخ می‌دهیم.
```

اتصال Business، مجوزها و قابلیت پاسخ‌گویی باید قبل از استفاده فعال و معتبر باشند.
