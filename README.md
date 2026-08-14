# TaskBot — ربات مدیریت تسک تلگرام

> ربات فارسی‌محور مدیریت وظایف، تیم‌ها، گزارش‌ها، عادت‌ها و اتصال به سرویس‌های بیرونی در Telegram.

TaskBot برای مدیریت چرخه کامل کار طراحی شده است: **ایجاد → اولویت → ددلاین → دسته‌بندی → مسئول → پیگیری → گزارش**.

## ✨ قابلیت‌ها

- ایجاد و مدیریت تسک
- اولویت، ددلاین، دسته‌بندی و تگ
- تعیین مسئول، تیم و برعهده گرفتن تسک
- وضعیت و تاریخچه تسک
- کامنت
- Mini Dashboard و فیلتر `/tasks`
- گزارش و خروجی CSV/Excel
- ورود گروهی CSV با اعتبارسنجی و Preview
- تاریخ جلالی
- مدیریت عادت
- دستیار هوشمند
- Jira و اتصال سرویس‌های مدیریت کار
- Guest Mode
- Telegram Business / Secretary Mode
- Telegram Stars
- Multi-Bot و ساخت ربات اختصاصی
- گزارش‌های تحت وب

## 🚀 شروع سریع

### نصب

```bash
git clone https://github.com/abolfazl260/task-mg-telegram-bot.git
cd task-mg-telegram-bot
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### اجرا

```bash
python main.py
```

حداقل تنظیمات:

```env
BOT_TOKEN=123456:ABC...
BOT_USERNAME=YourBot
```

## 📚 مستندات

مستندات اصلی از README جدا شده‌اند و در مسیر `docs/` نگهداری می‌شوند:

| موضوع | مستندات |
|---|---|
| معرفی و نقشه مستندات | [01 — معرفی](docs/01-overview.md) |
| نصب و اجرای پروژه | [02 — نصب](docs/02-installation.md) |
| متغیرهای محیطی و تنظیمات | [03 — تنظیمات](docs/03-configuration.md) |
| ایجاد، فیلتر و مدیریت تسک | [04 — مدیریت تسک‌ها](docs/04-task-management.md) |
| گزارش، CSV و ورود گروهی | [05 — گزارش‌ها و ورود اطلاعات](docs/05-reports-and-import.md) |
| AI، Jira و اتصال سرویس‌ها | [06 — یکپارچه‌سازی‌ها](docs/06-integrations.md) |
| Multi-Bot و Business Mode | [07 — ربات‌ها و Business](docs/07-bots-and-business.md) |
| معماری و دیتابیس | [08 — معماری](docs/08-architecture.md) |
| امنیت و عملیات Production | [09 — امنیت و عملیات](docs/09-security-and-operations.md) |
| توسعه و تست | [10 — توسعه](docs/10-development.md) |
| ماتریس قابلیت‌ها | [Feature Matrix](docs/FEATURE_MATRIX.md) |
| ورودی صوتی | [Voice Input](docs/voice-input.md) |
| استقرار Web App | [Web App Deployment](docs/webapp-deployment.md) |

## 🗂 ساختار مستندات

```text
docs/
├── 01-overview.md
├── 02-installation.md
├── 03-configuration.md
├── 04-task-management.md
├── 05-reports-and-import.md
├── 06-integrations.md
├── 07-bots-and-business.md
├── 08-architecture.md
├── 09-security-and-operations.md
├── 10-development.md
├── FEATURE_MATRIX.md
├── voice-input.md
└── webapp-deployment.md
```

## 🗄 دیتابیس

داده‌های اصلی پروژه در SQLite نگهداری می‌شوند:

```text
data/data.db
```

لایه دیتابیس از `aiosqlite` استفاده می‌کند و Schema شامل کاربران، تیم‌ها، تسک‌ها، کامنت‌ها، تاریخچه واگذاری، عادت‌ها، اتصال‌های خارجی، Jira، ربات‌های اختصاصی و Business Messages است.

## 🔐 امنیت

هیچ Token، API Key، OAuth Secret یا داده خصوصی کاربر نباید داخل Git Commit شود. جزئیات امنیت و عملیات در [مستندات امنیت](docs/09-security-and-operations.md) قرار دارد.

## 🧑‍💻 توسعه

برای توسعه، Handlerها، Serviceها و لایه دیتابیس باید از یکدیگر جدا بمانند. قبل از ارسال تغییرات:

```bash
pytest
```

راهنمای کامل در [مستندات توسعه](docs/10-development.md) قرار دارد.

## 📄 مجوز

شرایط استفاده و توزیع پروژه مطابق فایل `LICENSE` مخزن است.

## 🔗 Repository

https://github.com/abolfazl260/task-mg-telegram-bot
