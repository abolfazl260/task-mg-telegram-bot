# نصب و اجرای TaskBot

## پیش‌نیازها

- Python 3.10 یا بالاتر
- Bot Token از Telegram
- دسترسی اینترنت برای Telegram Bot API
- کلید سرویس‌های اختیاری در صورت فعال‌سازی قابلیت‌های مربوطه

## دریافت پروژه

```bash
git clone https://github.com/abolfazl260/task-mg-telegram-bot.git
cd task-mg-telegram-bot
```

## ساخت محیط مجازی

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

## تنظیم اولیه

فایل `.env` را در ریشه پروژه ایجاد کنید و حداقل Token ربات را قرار دهید. جزئیات متغیرها در [تنظیمات](03-configuration.md) آمده است.

## اجرای محلی

```bash
python main.py
```

## بررسی سریع

پس از اجرا:

1. ربات را در Telegram باز کنید.
2. `/start` را ارسال کنید.
3. با `/add` یک تسک آزمایشی بسازید.
4. با `/tasks` داشبورد و فیلترها را بررسی کنید.

## نکته دیتابیس

داده‌های اصلی پروژه در SQLite نگهداری می‌شوند و مسیر پیش‌فرض دیتابیس `data/data.db` است. لایه دیتابیس از `aiosqlite` استفاده می‌کند و SQLite با WAL و Foreign Key فعال پیکربندی شده است.
