# تنظیمات و متغیرهای محیطی

## تنظیمات پایه

```env
BOT_TOKEN=123456:ABC...
BOT_USERNAME=YourBot
```

## دستیار هوشمند

```env
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
```

## گزارش مدیریتی

```env
ADMIN_IDS=106056586,69078288
ADMIN_REPORT_TIME=20:00
```

## Secretary Mode

```env
SECRETARY_AUTO_REPLY_ENABLED=true
SECRETARY_AUTO_REPLY_TEXT=پیام شما دریافت شد؛ به‌زودی پاسخ می‌دهیم.
```

## چند ربات

برای اجرای چند Bot Profile می‌توان از ساختار زیر استفاده کرد:

```env
BOT_PROFILES=task_manager,request_workflow
BOT_TASK_MANAGER_TOKEN=123456:AAA...
BOT_TASK_MANAGER_USERNAME=TaskManagerPersian_Bot
BOT_REQUEST_WORKFLOW_TOKEN=987654:BBB...
BOT_REQUEST_WORKFLOW_USERNAME=RequestApproval_Bot
```

جزئیات ساختار پروفایل‌ها در [Multi-Bot و Business Mode](07-bots-and-business.md) آمده است.

## رمزنگاری Token ربات‌های Managed

برای Bot Profileهایی که token آن‌ها در دیتابیس ذخیره می‌شود، keyring رمزنگاری را در محیط deployment تنظیم کنید:

```env
BOT_TOKEN_ENCRYPTION_KEYS_JSON='{"2026-10":"<fernet-key>"}'
BOT_TOKEN_ACTIVE_KEY_ID=2026-10
```

برای ساخت key و migration/rotation به [Managed Bot Token Encryption](10-bot-token-encryption.md) مراجعه کنید.

## اصول نگهداری Secret

- Token و API Key را داخل کد Commit نکنید.
- `.env` را در Git قرار ندهید.
- برای production از Secret Management یا متغیرهای محیطی سرویس اجرا استفاده کنید.
- Token ربات‌های سفارشی کاربران باید مانند سایر Secretها محافظت شود.

## تنظیمات اختیاری

هر قابلیت اختیاری باید فقط در صورت وجود تنظیمات لازم فعال شود؛ برای مثال AI به `GROQ_API_KEY` و اتصال Jira به اطلاعات اتصال Jira نیاز دارد.
