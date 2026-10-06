# نقشه‌ی پروژه برای توسعه و کدنویسی هوش مصنوعی

این سند قراردادهای اصلی پروژه را توضیح می‌دهد تا قبل از تغییر کد، محل درست تغییر و مسیر اثر آن مشخص باشد.

## نمای کلی

```text
Telegram Update
  └─ main.py / handlers/
       └─ services/*
            └─ services/database.py → SQLite (data/data.db)

HTTP request
  └─ webapp/server.py
       ├─ webapp/auth.py / webapp/report_tokens.py
       ├─ webapp/tasks_api.py / webapp/clinic_api.py
       └─ services/* → SQLite / external APIs
```

## نقاط ورود

| مسیر | مسئولیت |
| --- | --- |
| `main.py` | ساخت یک Application تلگرام، ثبت command/callback/message handlerها و jobها |
| `bot_platform.py` | بارگذاری profileها، feature/permissionها و اجرای چند بات |
| `handlers/` | تبدیل Update به عملیات؛ محل پاسخ‌های فارسی و keyboardها |
| `services/` | منطق دامنه، اعتبارسنجی، تراکنش و اتصال به سرویس خارجی |
| `services/database.py` | اتصال async/sync، schema اصلی، transaction و helperهای SQL |
| `webapp/server.py` | HTTP server مستقل و dispatch مسیرهای Web App |
| `webapp/static/` | رابط کاربری وب؛ درخواست‌ها از طریق APIهای `webapp/` |
| `tests/` | تست‌های واحد، integration و قراردادهای routing/auth |

## دامنه‌ها

- **Tasks:** `services/task_service.py`؛ وضعیت‌ها `pending`, `in_progress`, `done`, `cancelled` و اولویت‌ها `low`, `medium`, `high` هستند.
- **Teams:** `services/team_service.py` و `services/team_manager.py`؛ دسترسی task تیمی از عضویت و نقش می‌آید.
- **Bots:** `bot_platform.py`، `services/bot_management_service.py` و `services/bot_runtime_manager.py`؛ هر profile `bot_key`، feature، permission و token مستقل دارد.
- **Reports:** `webapp/report_*` و `webapp/reports.py`؛ token گزارش در `web_report_tokens` ذخیره می‌شود.
- **Healthcare:** `services/healthcare/` و `webapp/clinic_api.py`؛ این بخش workspace/unit و policy دسترسی جدا دارد.
- **Integrations:** `services/integration_service.py`، Jira و OAuth؛ credentialها فقط از environment یا storage رمزنگاری‌شده خوانده شوند.

## جریان تغییر تسک

```text
handler یا webapp endpoint
  → احراز هویت و بررسی feature/permission
  → services.task_service
  → user_can_modify_task / team membership
  → transaction یا execute پارامتری
  → پاسخ Telegram یا JSON
```

برای عملیات جدید، کنترل دسترسی را در service هم نگه دارید؛ بررسی صرفاً در UI یا handler کافی نیست. `bot_key` برای انتخاب profile/runtime استفاده می‌شود و باید در مسیرهای Web App حفظ شود.

## مدل داده‌ی مهم

- `users`: هویت Telegram و تنظیمات کاربر
- `tasks`: taskهای شخصی/تیمی؛ taskهای core با `workspace_id IS NULL` شناخته می‌شوند
- `teams`, `team_members`: عضویت و نقش تیم
- `task_comments`, `task_assignment_history`: کامنت و تاریخچه‌ی واگذاری
- `custom_bots`, `bot_runtime_status`: profile و وضعیت اجرای بات
- `external_connections`, `oauth_pending_states`: اتصال‌های OAuth

Schema اولیه و indexها در `services/database.py` هستند؛ migrationهای healthcare/operations را در پوشه‌های همان دامنه بررسی کنید.

## قراردادهای امنیتی

1. `webapp/auth.py` باید Telegram `initData` را با HMAC و `auth_date` بررسی کند.
2. API ادمین ابتدا Telegram identity و سپس `is_admin` را بررسی می‌کند.
3. tokenهای گزارش دسترسی به داده می‌دهند؛ هر endpoint نوشتنی باید scope، مالکیت و انقضا را جداگانه بررسی کند.
4. شناسه‌های SQL از allowlist بیایند و مقادیر با parameter binding ارسال شوند.
5. محتوای کاربر در HTML با escape و در Markdown با احتیاط نمایش داده شود.

## روش بررسی تغییرات

```bash
python -m py_compile <changed-files.py>
python -m pytest -q tests/<relevant-test>.py
python -m pytest -q
```

در محیطی که dependencyها نصب نیستند، ابتدا `python -m pip install -r requirements.txt` را اجرا کنید. تست‌های مربوط به auth، task access، bot permissions و webapp برای تغییرات دسترسی الزامی‌اند.

## فایل‌هایی که نباید commit شوند

`data/data.db`، `.env`، tokenها، کلیدهای encryption، logهای runtime و فایل‌های generated نباید وارد Git شوند. قبل و بعد از تغییر، `git status --short` را بررسی کنید.
