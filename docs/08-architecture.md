# معماری و ساختار پروژه

## لایه‌ها

```text
handlers/  → دریافت Update و تعامل با کاربر
services/  → منطق کسب‌وکار و دسترسی به داده
utils/     → ابزارهای عمومی و Keyboard/Date helpers
config.py  → تنظیمات
main.py    → ساخت Application و ثبت Handlerها
```

## دیتابیس

دیتابیس اصلی SQLite در مسیر پیش‌فرض زیر قرار دارد:

```text
data/data.db
```

لایه دیتابیس از `aiosqlite` استفاده می‌کند و Schema شامل موجودیت‌هایی مانند Users، Teams، Tasks، Comments، Assignment History، Habits، Connections، Jira Links، Custom Bots و Business Messages است.

SQLite با موارد زیر تنظیم شده است:

- Foreign Keys فعال
- WAL
- `busy_timeout`
- Indexهای مربوط به Queryهای پرتکرار

## ساختار پیشنهادی پروژه

```text
.
├── main.py
├── config.py
├── bot_platform.py
├── bot_context.py
├── handlers/
├── services/
├── utils/
├── bots/
├── docs/
├── deploy/
├── samples/
├── data/
└── requirements.txt
```

## جریان یک درخواست

```text
Telegram Update
      ↓
Handler
      ↓
Service
      ↓
Database / Integration
      ↓
Response / Report
```

## اصل جداسازی مسئولیت

Handler نباید محل منطق پیچیده کسب‌وکار یا Queryهای سنگین باشد. منطق قابل استفاده مجدد باید در Service قرار گیرد و عملیات دیتابیس از مسیر لایه دیتابیس انجام شود.

برای داشبورد و گزارش‌ها، Queryهای aggregate مانند `COUNT` و `SUM` ترجیح دارند تا تمام Task Objectها بدون نیاز بارگذاری نشوند.
