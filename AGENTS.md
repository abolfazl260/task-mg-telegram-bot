# راهنمای عامل‌های توسعه

این فایل نقشه‌ی سریع پروژه برای توسعه‌دهنده‌ها و عامل‌های هوش مصنوعی است.

## قواعد تغییر

- منطق کسب‌وکار را در `services/` نگه دارید؛ handlerها باید ورودی Telegram/Web را به سرویس‌ها وصل کنند.
- Queryهای دیتابیس را پارامتری بنویسید و از ساختن SQL با ورودی کاربر خودداری کنید.
- تغییرات schema را در مسیر migration موجود بررسی کنید و از حذف یا reset کردن `data/data.db` خودداری کنید.
- توکن‌ها، کلیدها و فایل‌های `.env` را commit نکنید.
- برای تغییرات دسترسی، مسیر Telegram و Web App را هر دو بررسی کنید.
- قبل از commit، `python -m py_compile` برای فایل‌های تغییرکرده و تست مرتبط را اجرا کنید.

## نقاط شروع

- اجرای Telegram: `main.py` و `bot_platform.py`
- مدل و عملیات اصلی تسک: `services/task_service.py`
- دیتابیس و schema: `services/database.py`
- API وب: `webapp/server.py`، `webapp/tasks_api.py`
- احراز هویت Web App: `webapp/auth.py`
- مدیریت بات‌ها و featureها: `services/bot_management_service.py` و `services/bot_feature_registry.py`
- تست‌ها: `tests/`

نقشه‌ی کامل جریان داده و وابستگی‌ها در `docs/11-ai-project-context.md` است.
