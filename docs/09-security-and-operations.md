# امنیت و عملیات

## Secretها

هرگز این موارد را Commit نکنید:

- Bot Token
- Groq API Key
- Jira API Token
- OAuth Token و Refresh Token
- Token ربات‌های اختصاصی کاربران
- داده‌های خصوصی کاربران

نمونه صحیح:

```env
BOT_TOKEN=...
```

و در کد:

```python
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
```

## دیتابیس در Production

- از فایل دیتابیس Backup منظم بگیرید.
- دسترسی فایل `data/data.db` را محدود کنید.
- قبل از Migration نسخه Backup داشته باشید.
- SQLite WAL را هنگام کپی و Backup با روش مناسب مدیریت کنید.

## اجرای دائمی

در Production اجرای Bot بهتر است زیر یک Process Manager مانند systemd انجام شود تا پس از Restart سرور دوباره بالا بیاید.

نمونه بررسی وضعیت:

```bash
systemctl status taskbot
```

## خطای Token

```bash
python --version
pip install -r requirements.txt
python main.py
```

سپس `.env` و نام متغیر Token را بررسی کنید.

## خطای SQLite

در صورت خطای Query:

1. Schema فعلی را بررسی کنید.
2. نام و نوع ستون‌ها را با Query تطبیق دهید.
3. عملیات blocking را در Handler اجرا نکنید.
4. برای Queryهای آماری از عملیات سبک SQL استفاده کنید.

## Conflict در Git

```bash
git status
git fetch origin
```

اگر تغییرات Local مهم نیستند:

```bash
git reset --hard origin/main
git clean -fd
```

این دستورات تغییرات Commit نشده را حذف می‌کنند.

## نکته امنیتی گزارش تحت وب

هر URL گزارش وب باید دارای دسترسی امن و قابل اعتبارسنجی باشد. شناسه ساده و قابل حدس نباید به تنهایی برای مشاهده داده‌های خصوصی کافی باشد و endpoint باید دسترسی کاربر به داده را کنترل کند.
